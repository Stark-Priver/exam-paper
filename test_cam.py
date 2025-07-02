import cv2
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Cannot open camera")
    exit()
print("Camera opened successfully. Trying to read a frame...")
ret, frame = cap.read()
if ret:
    cv2.imwrite("test_camera.jpg", frame)
    print("Camera test successful, image saved to test_camera.jpg")
else:
    print("Cannot read frame from camera")
cap.release()