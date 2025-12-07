from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Depends
from typing import List, Optional
import shutil
import numpy as np
import os
import json

try:
    import cv2  # type: ignore[import-untyped]
except ImportError:
    raise ImportError(
        "opencv-python is required. Install it with: pip install opencv-python"
    )

# Type stubs for cv2 to suppress linter warnings (cv2 is a C extension)
# These are intentionally unreachable to provide type hints
if False:  # noqa: E501, PLR0124
    _ = cv2.imread  # type: ignore[attr-defined, unused-ignore]
    _ = cv2.cvtColor  # type: ignore[attr-defined, unused-ignore]
    _ = cv2.COLOR_BGR2RGB  # type: ignore[attr-defined, unused-ignore]

from api.schemas.dependencies import DatabaseServiceDep, get_database_service
from api.schemas.attendance import (
    UserCreate, UserGet, EnrollmentRequest, EnrollmentResponse,
    CourseCreate, CourseGet, LectureCreate, LectureGet,
    AttendanceMark, AttendanceGet, StudentCourseEnroll,
    AttendanceImageRequest, AttendanceImageResponse, RecognizedStudent
)

from database.models import UserRole, AttendanceStatus
from ai_module.facerecognition_service import FaceRecognitionService

router = APIRouter()
face_rec = FaceRecognitionService()


# User endpoints
@router.post("/users", response_model=UserGet)
async def create_user(user: UserCreate, service: DatabaseServiceDep):
    """Create a new user"""
    user_id = await service.create_user(
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        user_type=user.role,
        password_hash=user.password,
        profile_image=user.profile_image
    )
    
    created_user = await service.get_user_by_id(user_id)
    if not created_user or created_user.user_id is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")
    
    return UserGet(
        user_id=created_user.user_id,
        email=created_user.email,
        first_name=created_user.first_name,
        last_name=created_user.last_name,
        role=created_user.role,
        profile_image=created_user.profile_image
    )


@router.get("/users", response_model=list[UserGet])
async def get_users(service: DatabaseServiceDep):
    """Get all users"""
    from sqlmodel import select
    from database.models import User
    statement = select(User)
    result = await service.session.exec(statement)
    users = result.all()
    return [
        UserGet(
            user_id=user.user_id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            profile_image=user.profile_image
        ) for user in users
    ]


@router.get("/users/{user_id}", response_model=UserGet)
async def get_user(user_id: int, service: DatabaseServiceDep):
    """Get user by ID"""
    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return UserGet(
        user_id=user.user_id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        profile_image=user.profile_image
    )


# Enrollment endpoints
@router.post("/register", response_model=EnrollmentResponse)
async def register_user(
    service: DatabaseServiceDep,
    email: str = Form(...),
    password: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    role: str = Form("student"),
    images: list[UploadFile] = File(default=[])
):
    """
    Register a new user (student or doctor).
    - Students must provide exactly 5 face images.
    - Doctors can optionally provide images.
    """
    # Validate role
    try:
        user_role = UserRole(role.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {[r.value for r in UserRole]}"
        )

    # Validate image count based on role
    if user_role == UserRole.student:
        if len(images) != 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"For students, exactly 5 images are required. You provided {len(images)}."
            )

    # Check if user exists
    existing_user = await service.get_user_by_email(email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    # Create user
    user_id = await service.create_user(
        email=email,
        first_name=first_name,
        last_name=last_name,
        user_type=user_role,
        password_hash=password, # In production, hash this!
    )
    
    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")

    # Prepare upload directory
    upload_dir = f"uploads/{user_id}"
    os.makedirs(upload_dir, exist_ok=True)

    stored_count = 0
    first_valid_image_path = None
    
    # Process images if provided
    if images:
        for i, image_file in enumerate(images):
            # Save file to disk
            file_path = os.path.join(upload_dir, f"face_{i}_{image_file.filename}")
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(image_file.file, buffer)
                
            # Read image for processing
            image = cv2.imread(file_path)
            
            if image is None:
                # Try to delete invalid file
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                continue
                
            # Generate embedding (Pass BGR image directly)
            embedding = face_rec.get_embedding(image)
            
            if embedding is not None:
                await service.store_embedding(user_id, embedding, file_path)
                stored_count += 1
                
                # Set first valid image as profile image
                if first_valid_image_path is None:
                    first_valid_image_path = file_path

    # Update user profile image if we have one
    if first_valid_image_path:
        user.profile_image = first_valid_image_path
        await service.session.commit()
        await service.session.refresh(user)

    return EnrollmentResponse(
        user_id=user.user_id, # type: ignore
        email=user.email,
        full_name=f"{user.first_name} {user.last_name}",
        embeddings_stored=stored_count
    )


@router.post("/attendance/mark", response_model=AttendanceImageResponse)
async def mark_attendance_from_image(
    service: DatabaseServiceDep,
    lecture_id: int = Form(...),
    image: UploadFile = File(...)
):
    """
    Mark attendance from a lecture image.
    1. Detects faces in the uploaded image.
    2. Compares with stored embeddings using cosine similarity.
    3. Marks matched students as present for the given lecture.
    """
    # 1. Read and process the image
    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img_cv is None:
         raise HTTPException(status_code=400, detail="Invalid image file")

    # 2. Get embeddings from the uploaded image
    # Note: We need to detect ALL faces in the lecture hall image
    faces = face_rec.detect_faces(img_cv)
    
    recognized_students = []
    total_faces = len(faces)
    
    # Get all student embeddings from DB (This could be optimized to cache or filter by course)
    # For now, we fetch all and match. In production, load only students enrolled in the course.
    all_users_embeddings = await service.find_similar_faces(np.zeros(512), threshold=0.0, limit=1000) # Hack to get all? No, find_similar_faces logic is specific.
    
    # Let's implement a better matching strategy:
    # Iterate over each detected face in the lecture image
    for face in faces:
        detected_embedding = face.embedding
        
        # Find best match in DB
        # We need a method in service to find the BEST match for a single embedding
        matches = await service.find_similar_faces(detected_embedding, threshold=0.6, limit=1)
        
        if matches:
            best_match = matches[0]
            student_id = best_match['user_id']
            
            # Mark attendance in DB
            await service.mark_attendance(
                lecture_id=lecture_id,
                student_id=student_id,
                is_present=AttendanceStatus.present
            )
            
            recognized_students.append(RecognizedStudent(
                user_id=student_id,
                name=best_match['full_name'],
                email=best_match['email'],
                confidence=best_match['similarity']
            ))

    return AttendanceImageResponse(
        lecture_id=lecture_id,
        recognized_students=recognized_students,
        total_faces_detected=total_faces
    )

@router.get("/attendance/present", response_model=List[dict])
async def get_present_students_endpoint(
    service: DatabaseServiceDep,
    course_id: Optional[int] = None,
    doctor_id: Optional[int] = None
):
    """
    Get list of students present in lectures.
    Filter by course_id or doctor_id.
    """
    if not course_id and not doctor_id:
         raise HTTPException(status_code=400, detail="Either course_id or doctor_id must be provided")

    present_students = await service.get_present_students(course_id=course_id, doctor_id=doctor_id)
    return present_students



# Course endpoints
@router.post("/courses", response_model=CourseGet)
async def create_course(course: CourseCreate, service: DatabaseServiceDep):
    """Create a new course"""
    course_id = await service.create_course(
        course_name=course.course_name,
        course_code=course.course_code,
        doctor_id=course.doctor_id,
        description=course.description
    )
    
    # Get created course
    from sqlmodel import select
    from database.models import Course
    statement = select(Course).where(Course.course_id == course_id)
    result = await service.session.exec(statement)  # type: ignore[attr-defined, misc]
    created_course = result.first()
    
    if not created_course or created_course.course_id is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create course")
    
    return CourseGet(
        course_id=created_course.course_id,
        course_name=created_course.course_name,
        course_code=created_course.course_code,
        doctor_id=created_course.doctor_id,
        description=created_course.description
    )


@router.get("/courses", response_model=list[CourseGet])
async def get_courses(service: DatabaseServiceDep):
    """Get all courses"""
    from sqlmodel import select
    from database.models import Course
    statement = select(Course)
    result = await service.session.exec(statement)
    courses = result.all()
    return [
        CourseGet(
            course_id=course.course_id,
            course_name=course.course_name,
            course_code=course.course_code,
            doctor_id=course.doctor_id,
            description=course.description
        ) for course in courses
    ]


@router.post("/courses/enroll", status_code=status.HTTP_201_CREATED)
async def enroll_student_in_course(enrollment: StudentCourseEnroll, service: DatabaseServiceDep):
    """Enroll a student in a course"""
    await service.enroll_student_in_course(enrollment.student_id, enrollment.course_id)
    return {"message": "Student enrolled successfully"}


# Lecture endpoints
@router.post("/lectures", response_model=LectureGet)
async def create_lecture(lecture: LectureCreate, service: DatabaseServiceDep):
    """Create a new lecture"""
    lecture_id = await service.create_lecture(
        course_id=lecture.course_id,
        start_time=lecture.start_time,
        end_time=lecture.end_time,
        day_of_week=lecture.day_of_week,
        room_num=lecture.room_num
    )
    
    from sqlmodel import select
    from database.models import Lecture
    statement = select(Lecture).where(Lecture.lecture_id == lecture_id)
    result = await service.session.exec(statement)  # type: ignore[attr-defined, misc]
    created_lecture = result.first()
    
    if not created_lecture or created_lecture.lecture_id is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create lecture")
    
    return LectureGet(
        lecture_id=created_lecture.lecture_id,
        course_id=created_lecture.course_id,
        start_time=created_lecture.start_time,
        end_time=created_lecture.end_time,
        day_of_week=created_lecture.day_of_week,
        room_num=created_lecture.room_num
    )


@router.get("/lectures", response_model=list[LectureGet])
async def get_lectures(service: DatabaseServiceDep, course_id: int | None = None):
    """Get all lectures, optionally filtered by course_id"""
    from sqlmodel import select
    from database.models import Lecture
    
    if course_id:
        statement = select(Lecture).where(Lecture.course_id == course_id)
    else:
        statement = select(Lecture)
        
    result = await service.session.exec(statement)
    lectures = result.all()
    
    return [
        LectureGet(
            lecture_id=lecture.lecture_id,
            course_id=lecture.course_id,
            start_time=lecture.start_time,
            end_time=lecture.end_time,
            day_of_week=lecture.day_of_week,
            room_num=lecture.room_num
        ) for lecture in lectures
    ]


# Attendance endpoints
@router.post("/attendance/mark", response_model=AttendanceGet)
async def mark_attendance(attendance: AttendanceMark, service: DatabaseServiceDep):
    """Mark attendance for a student"""
    await service.mark_attendance(
        lecture_id=attendance.lecture_id,
        student_id=attendance.student_id,
        is_present=attendance.is_present
    )
    
    from sqlmodel import select
    from database.models import Attendance
    statement = select(Attendance).where(
        Attendance.lecture_id == attendance.lecture_id,
        Attendance.student_id == attendance.student_id
    )
    result = await service.session.exec(statement)  # type: ignore[attr-defined, misc]
    attendance_record = result.first()
    
    if not attendance_record:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to mark attendance")
    
    return AttendanceGet(
        lecture_id=attendance_record.lecture_id,
        student_id=attendance_record.student_id,
        is_present=attendance_record.is_present
    )


@router.get("/attendance", response_model=list[AttendanceGet])
async def get_attendance(service: DatabaseServiceDep, lecture_id: int | None = None, student_id: int | None = None):
    """Get attendance records, optionally filtered by lecture_id or student_id"""
    from sqlmodel import select
    from database.models import Attendance
    
    statement = select(Attendance)
    
    if lecture_id:
        statement = statement.where(Attendance.lecture_id == lecture_id)
    if student_id:
        statement = statement.where(Attendance.student_id == student_id)
        
    result = await service.session.exec(statement)
    records = result.all()
    
    return [
        AttendanceGet(
            lecture_id=record.lecture_id,
            student_id=record.student_id,
            is_present=record.is_present
        ) for record in records
    ]


@router.post("/attendance/image", response_model=AttendanceImageResponse)
async def take_attendance_from_image(
    service: DatabaseServiceDep,
    lecture_id: int = Form(...),
    threshold: float = Form(0.6),
    image_file: UploadFile = File(...)
):
    """Take attendance from an uploaded image using face recognition"""
    
    # Save temp file
    temp_path = f"temp_attendance_{lecture_id}.jpg"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(image_file.file, buffer)
        
    # Load and process image
    image = cv2.imread(temp_path)
    
    # Cleanup temp file immediately after reading
    try:
        os.remove(temp_path)
    except OSError:
        pass

    if image is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not load image")
    
    # Detect all faces in the image (Pass BGR)
    embeddings = face_rec.get_embeddings_multi(image)
    
    if not embeddings:
        return AttendanceImageResponse(
            lecture_id=lecture_id,
            recognized_students=[],
            total_faces_detected=0
        )
    
    # Match each face with database
    recognized_students = []
    
    for embedding in embeddings:
        matches = await service.find_similar_faces(embedding, threshold=threshold, limit=1)
        
        if matches and matches[0]['similarity'] > threshold:
            student = matches[0]
            # Mark attendance
            await service.mark_attendance(
                lecture_id=lecture_id,
                student_id=student['user_id'],
                is_present=AttendanceStatus.present
            )
            
            # Avoid duplicates in response if same student detected twice
            if not any(s['user_id'] == student['user_id'] for s in recognized_students):
                recognized_students.append({
                    'user_id': student['user_id'],
                    'name': student['full_name'],
                    'email': student['email'],
                    'confidence': student['similarity']
                })
    
    return AttendanceImageResponse(
        lecture_id=lecture_id,
        recognized_students=recognized_students,
        total_faces_detected=len(embeddings)
    )
