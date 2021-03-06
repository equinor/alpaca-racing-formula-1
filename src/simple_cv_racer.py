#!/usr/bin/env python3
import numpy as np
import cv2
from simple_pid import PID

import donkeycar as dk
from donkeycar.parts.datastore import TubHandler
from scipy.ndimage import convolve


class LineFollower:
    '''
    OpenCV based controller
    This controller takes a horizontal slice of the image at a set Y coordinate.
    Then it converts to HSV and does a color thresh hold to find the yellow pixels.
    It does a histogram to find the pixel of maximum yellow. Then is uses that iPxel
    to guid a PID controller which seeks to maintain the max yellow at the same point
    in the image.
    '''
    def __init__(self):
        self.vert_scan_y = 60   # num pixels from the top to start horiz scan
        self.vert_scan_height = 10 # num pixels high to grab from horiz scan
        self.color_thr_low = np.asarray((190, 190, 190)) # hsv dark yellow
        self.color_thr_hi = np.asarray((255, 255, 255)) # hsv light yellow
        self.target_pixel = None # of the N slots above, which is the ideal relationship target
        self.steering = 0.5 # from -1 to 1
        self.throttle = 0.15 # from -1 to 1
        self.recording = False # Set to true if desired to save camera frames
        self.delta_th = 0.1 # how much to change throttle when off
        self.throttle_max = 0.3
        self.throttle_min = 0.15
        self.pid_st = PID(Kp=-0.01, Ki=0.00, Kd=-0.001)

    
    def get_i_color(self, cam_img):
        '''
        get the horizontal index of the color at the given slice of the image
        input: cam_image, an RGB numpy array
        output: index of max color, value of cumulative color at that index, and mask of pixels in range 
        '''

        # take a horizontal slice of the image
        iSlice = self.vert_scan_y
        scan_line = cam_img[iSlice : iSlice + self.vert_scan_height, :, :]

        # convert to HSV color space
        img_hsv = scan_line # cv2.cvtColor(scan_line, cv2.COLOR_RGB2RGB)

        # make a mask of the colors in our range we are looking for
        mask = cv2.inRange(img_hsv, self.color_thr_low, self.color_thr_hi)
        
        for i in range(mask.shape[0]):
            for j in reversed(range(1, mask.shape[1] // 2)):
                mask[i, j - 1] = max(mask[i, j], mask[i, j - 1])

            for j in range(1 + cam_img.shape[1] // 2, cam_img.shape[1]):
                mask[i, j] = max(mask[i, j], mask[i, j - 1])
        
        # which index of the range has the highest amount of yellow?
        hist = np.sum(mask, axis=0)
        max_yellow = np.argmax(hist)

        return max_yellow, hist[max_yellow], mask


    def run(self, cam_img):
        '''
        main runloop of the CV controller
        input: cam_image, an RGB numpy array
        output: steering, throttle, and recording flag
        '''
        convkernel = np.ones((3, 3, 3)) / 27.
        # convkernel??[:, :, 2] *= 2

        # np.array([[1/9, 1/9, 1/9],[1/9, 1/9, 1/9],[1/9, 1/9, 1/9]])
        # cam_img[:, :, 0] = convolve(cam_img[:, :, 0], convkernel)
        # cam_img[:, :, 1] = convolve(cam_img[:, :, 1], convkernel)
        # cam_img[:, :, 2] = convolve(cam_img[:, :, 2], convkernel)

        # cam_img = convolve(cam_img, convkernel)

        
        max_yellow, confidense, mask = self.get_i_color(cam_img)
        conf_thresh = 0.01
        
        if self.target_pixel is None:
            # Use the first run of get_i_color to set our relationship with the yellow line.
            # You could optionally init the target_pixel with the desired value.
            self.target_pixel = max_yellow

            # this is the target of our steering PID controller
            self.pid_st.setpoint = self.target_pixel

        elif confidense > conf_thresh:
            # invoke the controller with the current yellow line position
            # get the new steering value as it chases the ideal
            self.steering = self.pid_st(max_yellow)
        
            # slow down linearly when away from ideal, and speed up when close
            if abs(max_yellow - self.target_pixel) > 10:
                if self.throttle > self.throttle_min:
                    self.throttle -= self.delta_th
            else:
                if self.throttle < self.throttle_max:
                    self.throttle += self.delta_th


        # show some diagnostics
        self.debug_display(cam_img, mask, max_yellow, confidense)

        return self.steering, self.throttle, self.recording


    def debug_display(self, cam_img, mask, max_yellow, confidense):
        '''
        composite mask on top the original image.
        show some values we are using for control
        '''

        mask_exp = np.stack((mask,)*3, axis=-1)
        iSlice = self.vert_scan_y
        img = np.copy(cam_img)
        img[iSlice : iSlice + self.vert_scan_height, :, :] = mask_exp
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        scale_percent = 400 # percent of original size
        width = int(img.shape[1] * scale_percent / 100)
        height = int(img.shape[0] * scale_percent / 100)
        dim = (width, height)
        img = cv2.resize(img, dim, interpolation = cv2.INTER_AREA)

        display_str = []
        display_str.append("STEERING:{:.1f}".format(self.steering))
        display_str.append("THROTTLE:{:.2f}".format(self.throttle))
        display_str.append("I YELLOW:{:d}".format(max_yellow))
        display_str.append("CONF:{:.2f}".format(confidense))

        y = 10
        x = 10

        for s in display_str:
            cv2.putText(img, s, color=(0,255,255), org=(x,y), fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=0.4)
            y += 10


        cv2.imwrite('test_image.png', mask)

        cv2.namedWindow('image', cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("image", cv2.WND_PROP_TOPMOST, 1)
        cv2.imshow("image", img)
        cv2.resizeWindow('image', 600, 500)
        cv2.waitKey(1)



def drive(cfg):
    '''
    Construct a working robotic vehicle from many parts.
    Each part runs as a job in the Vehicle loop, calling either
    it's run or run_threaded method depending on the constructor flag `threaded`.
    All parts are updated one after another at the framerate given in
    cfg.DRIVE_LOOP_HZ assuming each part finishes processing in a timely manner.
    Parts may have named outputs and inputs. The framework handles passing named outputs
    to parts requesting the same named input.
    '''
    print("Starting drive...")
    
    #Initialize car
    V = dk.vehicle.Vehicle()

    #Camera
    if cfg.DONKEY_GYM:
        from donkeycar.parts.dgym import DonkeyGymEnv
        cam = DonkeyGymEnv(cfg.DONKEY_SIM_PATH, host=cfg.SIM_HOST, env_name=cfg.DONKEY_GYM_ENV_NAME, conf=cfg.GYM_CONF, delay=cfg.SIM_ARTIFICIAL_LATENCY)
        inputs = ['steering', 'throttle']
    else:
        from donkeycar.parts.camera import PiCamera
        cam = PiCamera(image_w=cfg.IMAGE_W, image_h=cfg.IMAGE_H, image_d=cfg.IMAGE_DEPTH)
        inputs = []

    V.add(cam, inputs=inputs, outputs=['cam/image_array'], threaded=True)
        
    #Controller
    V.add(LineFollower(), 
          inputs=['cam/image_array'],
          outputs=['steering', 'throttle', 'recording'])

        
    #Drive train setup
    if not cfg.DONKEY_GYM:
        from donkeycar.parts.actuator import PCA9685, PWMSteering, PWMThrottle

        steering_controller = PCA9685(cfg.STEERING_CHANNEL, cfg.PCA9685_I2C_ADDR, busnum=cfg.PCA9685_I2C_BUSNUM)
        steering = PWMSteering(controller=steering_controller,
                                        left_pulse=cfg.STEERING_LEFT_PWM, 
                                        right_pulse=cfg.STEERING_RIGHT_PWM)
        
        throttle_controller = PCA9685(cfg.THROTTLE_CHANNEL, cfg.PCA9685_I2C_ADDR, busnum=cfg.PCA9685_I2C_BUSNUM)
        throttle = PWMThrottle(controller=throttle_controller,
                                        max_pulse=cfg.THROTTLE_FORWARD_PWM,
                                        zero_pulse=cfg.THROTTLE_STOPPED_PWM, 
                                        min_pulse=cfg.THROTTLE_REVERSE_PWM)

        V.add(steering, inputs=['steering'])
        V.add(throttle, inputs=['throttle'])
    
    #add tub to save data

    inputs=['cam/image_array',
            'steering', 'throttle']

    types=['image_array',
           'float', 'float']

    th = TubHandler(path=cfg.DATA_PATH)
    tub = th.new_tub_writer(inputs=inputs, types=types)
    V.add(tub, inputs=inputs, outputs=["tub/num_records"], run_condition="recording")

    #run the vehicle
    V.start(rate_hz=cfg.DRIVE_LOOP_HZ, 
            max_loop_count=cfg.MAX_LOOPS)


if __name__ == '__main__':
    cfg = dk.load_config()
    drive(cfg)
