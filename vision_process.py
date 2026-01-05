import cv2
from picamera2 import Picamera2
import time
import numpy as np
import multiprocessing
import argparse
from collections import deque
from ultralytics import YOLO
import logging
import os

class VisionProcess:
    def __init__(self, audio_queue, logger_instance, audio_playing_flag, model_path='yolov8n.pt'):
        """
        Initialize the Vision & Monitoring Process.
        Args:
            audio_queue: A multiprocessing.Queue to send audio requests.
            logger_instance: The logger instance configured for this process.
            audio_playing_flag: A multiprocessing.Event to check if audio is playing.
            model_path: Path to the YOLO model weights.
        """
        self.audio_queue = audio_queue
        self.logger = logger_instance
        self.audio_playing_flag = audio_playing_flag
        self.initialization_failed = False
        
        try:
            self.logger.info("Initializing camera with Picamera2...")
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration(main={"size": (640, 480)})
            self.picam2.configure(config)
            self.picam2.start()
            time.sleep(1)

            self.logger.info(f"Loading YOLO model from '{model_path}'...")
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"YOLO model file not found at: {model_path}")
            self.model = YOLO(model_path)

        except Exception as e:
            self.logger.error(f"CRITICAL: Vision process failed to initialize: {e}", exc_info=True)
            self.initialization_failed = True

        self.THRESHOLDS = {
            'low_crowd': 5, 'medium_crowd': 15, 'high_crowd': 25,
            'distance_threshold': 100, # pixels
            'queue_cluster_size': 5,
            'close_distance_warning': 80 # pixels
        }
        
        self.MESSAGES = {
            'social_distance': "social_distance.mp3",
            'close_proximity': "close_proximity.mp3",
            'wear_mask': "wear_mask.mp3",
            'cough_sneeze_detected': "cough_sneeze.mp3",
            'queue_forming': "queue_forming.mp3",
            'overcrowding': "overcrowding.mp3",
        }
        
        self.crowd_count = 0
        self.last_announcement_time = {}
        self.announcement_cooldown = 10  # seconds
        
        self.shutdown_flag = multiprocessing.Event()
        if not self.initialization_failed:
            self.logger.info("Vision Process initialized successfully")

    def detect_people(self, frame):
        """Detect people in the frame using YOLO."""
        results = self.model(frame, classes=[0], verbose=False)
        detections = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                if float(box.conf[0]) > 0.5:
                    detections.append([x1, y1, x2, y2])
        return detections

    def calculate_centroids(self, detections):
        """Calculate center points of detected people."""
        return [((d[0] + d[2]) // 2, (d[1] + d[3]) // 2) for d in detections]

    def check_social_distancing(self, centroids):
        """Check for social distancing violations."""
        violations = []
        critical_violations = []
        for i in range(len(centroids)):
            for j in range(i + 1, len(centroids)):
                dist = np.linalg.norm(np.array(centroids[i]) - np.array(centroids[j]))
                if dist < self.THRESHOLDS['close_distance_warning']:
                    critical_violations.append((i, j))
                elif dist < self.THRESHOLDS['distance_threshold']:
                    violations.append((i, j))
        return violations, critical_violations

    def detect_queue_formation(self, centroids):
        """
        Detect if people are forming queues (clustering).
        Returns:
            bool: True if a queue is detected.
        """
        if len(centroids) < self.THRESHOLDS['queue_cluster_size']:
            return False

        # Simple clustering based on proximity
        clusters = []
        visited = set()
        for i, point in enumerate(centroids):
            if i in visited:
                continue
            
            cluster = {i}
            # Iteratively find all points belonging to this cluster
            queue = [i]
            head = 0
            while head < len(queue):
                current_person_idx = queue[head]
                head += 1
                
                for j, other_point in enumerate(centroids):
                    if j in visited or j in cluster:
                        continue
                    
                    dist = np.linalg.norm(np.array(centroids[current_person_idx]) - np.array(other_point))
                    if dist < self.THRESHOLDS['distance_threshold'] * 1.5:
                        cluster.add(j)
                        queue.append(j)

            visited.update(cluster)
            if len(cluster) >= self.THRESHOLDS['queue_cluster_size']:
                # Check if the cluster forms a line (high aspect ratio)
                points = np.array([centroids[i] for i in cluster])
                if len(points) < 2: self.logger.debug("Not enough points for PCA in queue detection."); continue
                
                try:
                    mean, eigenvectors = cv2.PCACompute(points, mean=None)
                    if eigenvectors is None or len(eigenvectors) < 2: 
                        self.logger.debug("PCACompute returned insufficient eigenvectors in queue detection."); 
                        continue
                    aspect_ratio = np.linalg.norm(eigenvectors[0]) / (np.linalg.norm(eigenvectors[1]) + 1e-6)
                    if aspect_ratio > 2.5: # A high ratio means it's more line-like
                        self.logger.info(f"Line-like cluster detected with aspect ratio {aspect_ratio:.2f}")
                        return True
                except cv2.error as e:
                    self.logger.warning(f"OpenCV error during PCACompute: {e}")
                    continue
        return False

    def analyze_crowd(self, detections, centroids):
        """Analyze crowd and queue audio announcements."""
        current_time = time.time()
        self.crowd_count = len(detections)

        # Overcrowding
        if self.crowd_count >= self.THRESHOLDS['high_crowd']:
            if self._can_announce('overcrowding', current_time):
                self.queue_announcement(self.MESSAGES['overcrowding'])
                self.logger.warning(f"Overcrowding detected: {self.crowd_count} people")

        # Social distancing
        violations, critical_violations = self.check_social_distancing(centroids)
        if len(critical_violations) > 0:
            if self._can_announce('close_proximity', current_time, cooldown=5):
                self.queue_announcement(self.MESSAGES['close_proximity'])
                self.logger.warning(f"Critical proximity violations: {len(critical_violations)} pairs")
        elif len(violations) > 2:
            if self._can_announce('social_distance', current_time):
                self.queue_announcement(self.MESSAGES['social_distance'])
                self.logger.warning(f"Social distancing violations: {len(violations)} pairs")

        # Queue detection
        if self.detect_queue_formation(centroids):
            if self._can_announce('queue_forming', current_time):
                self.queue_announcement(self.MESSAGES['queue_forming'])
                self.logger.info("Queue formation detected and announced.")

    def _can_announce(self, msg_type, current_time, cooldown=None):
        """Check announcement cooldown."""
        cooldown = cooldown or self.announcement_cooldown
        last_time = self.last_announcement_time.get(msg_type, 0)
        if (current_time - last_time) > cooldown:
            self.last_announcement_time[msg_type] = current_time
            return True
        return False

    def queue_announcement(self, message):
        """Send an announcement request to the audio manager."""
        if self.audio_playing_flag.is_set():
            self.logger.info(f"Vision: Deferring announcement '{message}' because audio is already playing.")
            return

        try:
            audio_request = {'command': 'play', 'file': message}
            self.logger.info(f"Vision: Queueing audio request '{audio_request}'")
            self.audio_queue.put(audio_request)
        except Exception as e:
            self.logger.error(f"Failed to queue announcement: {e}")

    def draw_detections(self, frame, detections, centroids, violations, critical_violations):
        """Draw detections and info on the frame."""
        for i, det in enumerate(detections):
            x1, y1, x2, y2 = det
            color = (0, 255, 0); is_critical = any(i in v for v in critical_violations); is_violation = any(i in v for v in violations)
            if is_critical: color = (0, 0, 255)
            elif is_violation: color = (0, 165, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.circle(frame, centroids[i], 5, color, -1)
        info_text = f"People: {self.crowd_count} | Violations: {len(violations)}"
        cv2.putText(frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        return frame

    def run(self, display=True):
        """Main loop for the vision system."""
        if self.initialization_failed:
            self.logger.error("Cannot start VisionProcess run loop because initialization failed.")
            return

        self.logger.info("Vision process running...")
        frame_skip = 5
        frame_count = 0
        try:
            while not self.shutdown_flag.is_set():
                try:
                    frame = self.picam2.capture_array()
                except Exception as e:
                    self.logger.error(f"Failed to capture frame from camera: {e}")
                    time.sleep(2) # Wait a bit before trying again
                    continue

                if frame.shape[2] == 4:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)

                frame_count += 1
                if frame_count % frame_skip != 0:
                    if display: cv2.imshow('Vision Process', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'): break
                    continue

                detections = self.detect_people(frame)
                centroids = self.calculate_centroids(detections)
                self.analyze_crowd(detections, centroids)
                
                if display:
                    violations, critical = self.check_social_distancing(centroids)
                    frame = self.draw_detections(frame, detections, centroids, violations, critical)
                    cv2.imshow('Vision Process', frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.logger.info("Quit command received from display window.")
                    break
        finally:
            self.stop()

    def stop(self):
        """Clean up resources."""
        self.logger.info("Shutting down Vision Process...")
        if hasattr(self, 'picam2') and self.picam2.started:
            self.picam2.stop()
        cv2.destroyAllWindows()
        self.logger.info("Vision Process stopped.")

def vision_process_func(audio_queue, shutdown_flag, audio_playing_flag):
    """Target function for the multiprocessing.Process."""
    import logging # Explicitly import logging for this process function
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    process_logger = logging.getLogger("VisionProcess") # Get logger AFTER basicConfig
    vision_system = VisionProcess(audio_queue, process_logger, audio_playing_flag) # Pass the logger instance
    vision_system.shutdown_flag = shutdown_flag
    vision_system.run()

if __name__ == "__main__":
    # For independent testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    test_logger = logging.getLogger("VisionProcessTest") # Get a logger for the test block
    test_logger.info("Testing Vision Process independently...")
    audio_q = multiprocessing.Queue()
    shutdown_event = multiprocessing.Event()

    def audio_listener(q):
        import logging # Re-import logging for the listener process
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        listener_logger = logging.getLogger("AudioListener")
        while True:
            try: msg = q.get(timeout=5)
            except: break
            if msg == "shutdown": break
            listener_logger.info(f"[TEST LISTENER] Heard: {msg}")

    listener_proc = multiprocessing.Process(target=audio_listener, args=(audio_q,))
    listener_proc.start()

    try:
        # Pass the logger to the VisionProcess for independent testing as well
        vision_proc = VisionProcess(audio_q, test_logger) 
        vision_proc.shutdown_flag = shutdown_event
        vision_proc.run()
    except KeyboardInterrupt:
        test_logger.info("Test stopped by user.")
    finally:
        shutdown_event.set()
        if 'listener_proc' in locals() and listener_proc.is_alive():
            audio_q.put("shutdown")
            listener_proc.join()
    test_logger.info("Vision Process test complete.")