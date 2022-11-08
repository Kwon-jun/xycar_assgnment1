#!/usr/bin/env python
# -*- coding: utf-8 -*-

from types import NoneType
import numpy as np
import cv2, math
import rospy, rospkg, time
from sensor_msgs.msg import Image
from sensor_msgs.msg import CompressedImage
from geometry_msgs.msg import PoseStamped

from cv_bridge import CvBridge
from xycar_msgs.msg import xycar_motor
from math import *
import signal
import sys
import os
import random
#import keyboard

import time


def signal_handler(sig, frame):
    import time
    time.sleep(3)
    os.system('killall -9 python rosout')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

class Robotvisionsystem:
    def __init__(self):
        self.image = np.empty(shape=[0]) 
        self.bridge = CvBridge() 
        self.motor = None 
        self.angle = 0
        self.speed = 0.1
        self.stop = 0
        self.trig = 0
        self.turn_trig = 0
        self.right_thresh = 0
        self.left_thresh= 0
        self.center_thresh = 0
        self.save_time = 0
        self.mode = 0

        self.past_left_center = 0
        self.past_right_center = 0
        self.past_line_center = 0

        self.CAM_FPS = 30
        self.WIDTH, self.HEIGHT = 640, 480

        rospy.init_node('driving')
        
        self.motor = rospy.Publisher('xycar_motor', xycar_motor, queue_size=1)
        self.unitymotor = rospy.Publisher('unitymotor', PoseStamped, queue_size=1)
        self.image_sub = rospy.Subscriber("/unitycamera", CompressedImage , self.img_callback)
        # image_sub = rospy.Subscriber("/usb_cam/image_raw",CompressedImage,img_callback)

        print ("----- Xycar self driving -----")
        self.start()



    def img_callback(self, data):
        # print data
        try:
            self.image = self.bridge.compressed_imgmsg_to_cv2(data, "bgr8") # mono8, mono16, bgr8, rgb8, bgra8, rgba8, passthrough
        except CvBridgeError as e:
            print("___Error___")
            print(e)
        
        # np_arr = np.formstring(data, np.unit8)
        # self.image = cv2.imdecode(np_arr, cv2.CV_LOAD_IMAGE_COLOR)
    
    def trackbar(self):
        img = self.image
        hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)
        cv2.namedWindow("Trackbar Windows")
        cv2.createTrackbar("L-High", "Trackbar Windows", 0, 255, lambda x: x)
        cv2.createTrackbar("L-Low", "Trackbar Windows", 0, 255, lambda x: x)

        cv2.setTrackbarPos("L-High","Trackbar Windows", 255)
        cv2.setTrackbarPos("L-Low" ,"Trackbar Windows", 110)
        
        print ":::::"
        while cv2.waitKey(1) != ord('q'):
            L_h = cv2.getTrackbarPos("L-High", "Trackbar Windows")
            L_l = cv2.getTrackbarPos("L-Low" , "Trackbar Windows")
            HLS = cv2.inRange(hls, (0, L_l, 0), (255, L_h, 255))
            hls_out = cv2.bitwise_and(hls, hls, mask = HLS)
            result = cv2.cvtColor(hls_out, cv2.COLOR_HSV2BGR)
            cv2.imshow("Trackbar Windows", result)
        
        cv2.destoryAllWindows()


    def trackbar_canny(self):
        img = self.image
        
        
        print ":::::"
        while cv2.waitKey(1) != ord('q'):
            blur = cv2.GaussianBlur(img, (5, 5), 0)
            H, L, S = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HLS))
            _, L = cv2.threshold(L, 75, 110, cv2.THRESH_BINARY)
            edge_img = cv2.Canny(np.uint8(L), 60, 70)
            cv2.imshow("Trackbar Windows", edge_img)
        
        cv2.destoryAllWindows()


    def drive(self, angle, speed):
        
        motor_msg = xycar_motor()
        motor_msg.angle = angle
        motor_msg.speed = speed

        self.motor.publish(motor_msg)

    def unitydrive(self, angle, speed):

        unitymotor_msg = PoseStamped()
        unitymotor_msg.pose.position.x = speed
        unitymotor_msg.pose.orientation.x = angle

        self.unitymotor.publish(unitymotor_msg) 

    def start(self):
        while not self.image.size == (self.WIDTH * self.HEIGHT * 3): continue
        print("==> Complete Load Image ")
        while not rospy.is_shutdown(): # Main Loop
            #self.trackbar_canny()
            #self.unitydrive(0, 0.1)
            
            # Task1 : Use OpenCV for Robotvisionsystem
            
            self.current_time = rospy.get_time()

            
            
            #img = self.image.copy()

            img = self.image
            blur = cv2.GaussianBlur(img, (5, 5), 0)
            H, L, S = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HLS))
            _, L = cv2.threshold(L, 75, 110, cv2.THRESH_BINARY)
            edge_img = cv2.Canny(np.uint8(L), 60, 70)

            


            
            
            ## White line ##########################################
            if self.stop == 0:
                # print("Flag stop == 0")
                #line_roi = edge_img[360:480, 80:560]
                line_roi = edge_img[360:480, 80:560]

                # HoughLinesP
                all_lines = cv2.HoughLinesP(line_roi, 1, math.pi/180,30,30,10)
                #print ("all_line", all_lines)
                
                if all_lines is None:
                    print ("nonono")
                    all_lines = [[[0, 0, 0, 0]]]


                # draw lines in ROI area
                line_img = line_roi.copy()  ##### line

                for line in all_lines:
                    x1, y1, x2, y2 = line[0]
                    cv2.line(line_img, (x1, y1+240), (x2, y2+240), (0, 255, 0), 2)
                
                # calculate slope and do filtering
                slopes = []
                new_lines = []
                for line in all_lines:
                    x1, y1, x2, y2 = line[0]
                    if (x2 - x1) == 0:
                        slope = 0
                    else:
                        slope = float(y2-y1) / float(x2-x1)
                    if 0.1 < abs(slope) < 10:
                        slopes.append(slope)
                        new_lines.append(line[0])

                # divide lines left and right
                left_lines = []
                right_lines = []
                for j in range(len(slopes)):
                    Line = new_lines[j]
                    slope = slopes[j]
                    x1, y1, x2, y2 = Line
                    if (slope < 0) and (x2 < 320):
                        left_lines.append([Line.tolist()])
                    elif (slope > 0) and (x1 > 320):
                        right_lines.append([Line.tolist()])

                # draw right&left lines in different color
                line_img = line_roi.copy()
                for line in left_lines:
                    x1, y1, x2, y2 = line[0]
                    cv2.line(self.image, (x1, y1+240), (x2, y2+240), (0, 0, 255), 2)

                for line in right_lines:
                    x1, y1, x2, y2 = line[0]
                    cv2.line(self.image, (x1, y1+240), (x2, y2+240), (0, 255, 255), 2)

                # get average left-line
                x_sum, y_sum, m_sum = 0.0, 0.0, 0.0
                size = len(left_lines)

                for line in left_lines:
                    x1, y1, x2, y2 = line[0]
                    x_sum += x1 + x2
                    y_sum += y1 + y2
                    m_sum += float(y2 - y1) / float(x2 - x1)
                    x_avg = x_sum / (size * 2)
                    y_avg = y_sum / (size * 2)
                    m_left = m_sum / size
                    b_left = y_avg - m_left * x_avg

                x1 = int((0.0 - b_left) / m_left)
                x2 = int((240.0 - b_left) / m_left)
                left_center = int((x1+x2)/2)
                cv2.line(self.image, (x1, 0+240), (x2, 240+240), (255, 0, 0), 2)

                x_sum, y_sum, m_sum = 0.0, 0.0, 0.0
                size = len(right_lines)
                for line in right_lines:
                    x1, y1, x2, y2 = line[0]
                    x_sum += x1 + x2
                    y_sum += y1 + y2
                    m_sum += float(y2 - y1) / float(x2 - x1)
                    x_avg = x_sum / (size * 2)
                    y_avg = y_sum / (size * 2)
                    m_right = m_sum / size
                    b_right = y_avg - m_right * x_avg

                x1 = int((0.0 - b_right) / m_right)
                x2 = int((240.0 - b_right) / m_right)
                right_center = int((x1+x2)/2)
                cv2.line(self.image, (x1, 0+240), (x2, 240+240), (255, 0, 0), 2)
                
                line_center = int((left_center + right_center)/2)

                #Car center
                cv2.line(self.image, (0, 360), (640, 360), (0, 255, 255), 1)
                cv2.rectangle(self.image, (315, 355), (325, 365), (0, 0, 255), 2)

                # Draw Rectangle
                cv2.rectangle(self.image, (left_center-5, 355), (left_center+5, 365), (0, 255, 0), 2)   #left line center rectangle
                cv2.rectangle(self.image, (right_center-5, 355), (right_center+5, 365), (0, 255, 0), 2) #right line center rectangle
                cv2.rectangle(self.image, (line_center-5, 355), (line_center+5, 365), (0, 255, 0), 2)   #car center rectangle

                '''
                if self.trig == 0:
                    self.right_thresh = right_center
                    self.left_thresh = left_center
                    self.center_thresh = line_center
                    self.trig = 1

                self.angled = right_center - self.right_thresh
                self.angled = self.angled * 0.2
                '''

                
                
                if self.mode == 0:

                    if self.trig == 0:
                        self.right_thresh = right_center
                        self.left_thresh = left_center
                        self.center_thresh = line_center
                        self.trig = 1

                    self.angled =  self.center_thresh - line_center
                
                    if right_center < 360 or right_center > 500: #left_center < 0
                        
                        if self.turn_trig == 0:
                            self.save_time = self.current_time
                            self.turn_trig = 1
                    else:
                        self.angled = self.angled * 0.1
                        
                        
                    if self.turn_trig == 1:
                        if self.save_time + 10 < self.current_time:   #turn
                            self.turn_trig = 0
                            self.trig = 0
                            self.mode = 1
                        elif self.save_time +2 > self.current_time:
                            #self.angled = self.angled * 0.1
                            self.angled = 0
                        else:
                            self.angled = -25

                elif self.mode==1:

                    if self.turn_trig == 0:
                        self.save_time = self.current_time
                        self.turn_trig = 1

                    if self.save_time + 14 < self.current_time:   #go
                        self.turn_trig = 0
                        self.trig = 0
                        #self.angled = 0
                        self.mode = 2
                            
                    else:
                        #if right_center < 360 or right_center > 500:

                        if left_center < 0:
                            self.angled = -200 - left_center
                            if self.past_left_center == left_center:
                                self.angled = 0
                        
                        else:
                            self.angled = 70 - left_center
                            #self.angle = 0
                            
                        self.angled = self.angled * 0.1

                        if self.angled > 5:
                            self.angled = 5
                        elif self.angled < -5:
                            self.angled = -5
                        # else:
                        #     self.angled = 420 - right_center
                        #     self.angled = self.angled * 0.1


                elif self.mode ==2:
                    
                    # if self.trig == 0:
                    #     self.right_thresh = right_center
                    #     self.left_thresh = left_center
                    #     self.center_thresh = line_center
                    #     self.trig = 1

                    #self.angled = right_center - 470
                    self.angled = 0 
                        
                    if left_center < 0: #right_center < 360 or right_center > 600: 
                        
                        if self.turn_trig == 0:
                            self.save_time = self.current_time
                            self.turn_trig = 1
                    else:
                        self.angled = self.angled * 0.1

                    if self.turn_trig == 1:
                        if self.save_time + 10 < self.current_time:   #turn
                            self.turn_trig = 0
                            self.trig = 0
                            self.mode = 3
                        elif self.save_time +2 > self.current_time:
                            #self.angled = self.angled * 0.1
                            self.angled = 0
                        else:
                            self.angled = -25
                    
                elif self.mode == 3:
                    
                    # if self.trig == 0:
                    #     self.right_thresh = right_center
                    #     self.left_thresh = left_center
                    #     self.center_thresh = line_center
                    #     self.trig = 1

                    if self.turn_trig == 0:
                        self.save_time = self.current_time
                        self.turn_trig = 1

                    if self.save_time + 10 < self.current_time:   #go
                        self.turn_trig = 0
                        self.trig = 0
                        #self.angled = 0
                        self.mode = 4
                            
                    else:
                        self.angled = 420 - right_center
                        #self.angled = 240 - line_center

                        self.angled = self.angled * 0.1

                        if self.angled > 5:
                            self.angled = 5
                        elif self.angled < -5:
                            self.angled = -5

                    
                        # self.angled = left_center - self.left_thresh
                        # self.angled = self.angled * 0.1

                elif self.mode ==4:
                    # self.angled = 0
                    # self.speed = 0
                    
                    #self.angled = 0 
                        
                    if (right_center < 360 or right_center > 550) and left_center < 0: # left_center < 0: #
                        
                        if self.turn_trig == 0:
                            self.save_time = self.current_time
                            self.turn_trig = 1
                    else:
                        self.angled = self.angled * 0.1

                    if self.turn_trig == 1:
                        if self.save_time + 10 < self.current_time:   #turn
                            self.turn_trig = 0
                            self.trig = 0
                            self.mode = 5
                        elif self.save_time +2 > self.current_time:
                            self.angled = 0
                            self.angled = self.angled * 0.1
                        else:
                            self.angled = -25


                elif self.mode ==5:
                    if self.turn_trig == 0:
                        self.save_time = self.current_time
                        self.turn_trig = 1

                    if self.save_time + 2 < self.current_time:   #go
                        self.turn_trig = 0
                        self.trig = 0
                        #self.angled = 0
                        self.mode = 6
                    else:
                        #self.angled = 0

                        if left_center < 0:
                            self.angled = -180 - left_center
                        else:
                            self.angled = 50 - left_center
                        self.angled = self.angled * 0.1

                        if self.angled > 8:
                            self.angled = 8
                        elif self.angled < -8:
                            self.angled = -8
                
                elif self.mode ==6:
                    # self.angled = 0
                    # self.speed = 0

                    if right_center < 360 or right_center > 500: # left_center < -30: 
                        if self.turn_trig == 0:
                            self.save_time = self.current_time
                            self.turn_trig = 1
                    else:
                        self.angled = self.angled * 0.1

                    if self.turn_trig == 1:
                        if self.save_time + 10 < self.current_time:   #turn
                            self.turn_trig = 0
                            self.trig = 0
                            self.mode = 7
                        else:
                            self.angled = -25


                elif self.mode == 7:
                    if self.turn_trig == 0:
                        self.save_time = self.current_time
                        self.turn_trig = 1

                    if self.save_time + 8 < self.current_time:   #go
                        
                        self.turn_trig = 0
                        self.trig = 0
                        #self.angled = 0
                        self.mode = 8
                    else:
                        self.angled = 70 - left_center
                        self.angled = self.angled * 0.1



                elif self.mode == 8:
                    # self.angled = 0
                    # self.speed = 0
                    if right_center < 360 or right_center > 500:
                        
                        if self.turn_trig == 0:
                            self.save_time = self.current_time
                            self.turn_trig = 1
                    else:
                        self.angled = 70 - left_center
                        self.angled = self.angled * 0.1

                    if self.turn_trig == 1:
                        if self.save_time + 14 < self.current_time:   #turn
                            self.turn_trig = 0
                            self.trig = 0
                            self.mode = 9
                        elif self.save_time + 3 > self.current_time:
                            self.angled = 0
                        else:
                            self.angled = 20

                elif self.mode == 9:
                    # self.angled = 0
                    # self.speed = 0

                    if self.turn_trig == 0:
                        self.save_time = self.current_time
                        self.turn_trig = 1

                    if self.save_time + 2 < self.current_time:   #go
                        self.turn_trig = 0
                        self.trig = 0
                        #self.angled = 0
                        self.mode = 10
                    else:
                        self.angled = 0

                    

                elif self.mode == 10:
                    if self.turn_trig == 0:
                        self.save_time = self.current_time
                        self.turn_trig = 1

                    if self.save_time + 11 < self.current_time:   #go
                        self.turn_trig = 0
                        self.trig = 0
                        #self.angled = 0
                        self.mode = 11
                    else:
                        self.angled = 20





                elif self.mode == 11:
                    # self.angled = 0
                    # self.speed = 0

                    if self.turn_trig == 0:
                        self.save_time = self.current_time
                        self.turn_trig = 1

                    if self.save_time + 5 < self.current_time:   #go
                        self.turn_trig = 0
                        self.trig = 0
                        #self.angled = 0
                        self.mode = 12
                    else:
                        self.angled = 420 - right_center
                        self.angled = self.angled * 0.1

                elif self.mode == 12:
                    self.angled = 0
                    self.speed = 0
                
                
                
                

                

                
                if self.angled > 50:
                    self.angled = 30
                elif self.angled < -50:
                    self.angled = -30

                # if all_lines is None:
                #     #self.angled = self.angled * 0.1
                #     self.angled = 0
                

                print("Line center : ", line_center)
                print("left center : ", left_center)
                print("right center : ", right_center)
                print("angled : ", self.angled)
                print("save time : ", self.save_time)
                print("time : ", self.current_time)
                print("mode : ", self.mode)
                print("self.past_left_center : ", self.past_left_center)

                # self.past_left_center = 0
                # self.past_right_center = 0
                # self.past_line_center = 0

                # self.past_left_center = left_center
                # self.past_right_center = right_center
                # self.past_line_center = line_center

            
            # except:
            #     print("Error whiteline")
            ################################################################
            '''
            ## Stop line ROI Area ##########################################
            #640x480
            stop_x_min = 240
            stop_x_max = 400
            stop_y_min = 370
            stop_y_max = 410
            stop_roi = L.copy()
            stop_roi = stop_roi[stop_y_min:stop_y_max, stop_x_min:stop_x_max] # y,x
            # try:
            _, contours, _ = cv2.findContours(stop_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            # print("contours : ", contours)
            for cont in contours:
                length = cv2.arcLength(cont, True)
                area = cv2.contourArea(cont)
                # print("Stop Flag : ", self.stop, "Area :", area, "Length : ", length)

                if not ((2000 > area > 1200) and (length > 300)):
                    continue

                # print("Len : ", len(cv2.approxPolyDP(cont, length*0.02, True)))
                if len(cv2.approxPolyDP(cont, length*0.02, True)) < 2:
                    continue
                
                (x, y, w, h) = cv2.boundingRect(cont)
                center = (x + int(w/2), y + int(h/2))

                if (70 <= center[0] <= (stop_x_max - stop_x_min)) and (self.stop == 0):
                    cv2.rectangle(self.image, (x+stop_x_min, y+stop_y_min), (x + w + stop_x_min, y + h + stop_y_min), (0, 255, 0), 2)
                    self.stop += 1
                    self.past_time = self.current_time
                    print "stopline"
                
                if self.stop == 1:
                    print("Flag stop == 1")
                    self.past_time = self.current_time
                    while self.current_time - self.past_time <= 5:
                        self.current_time = rospy.get_time()
                        self.angled = 0
                        self.speed = 0
                        self.drive(self.angled, self.speed)                    
                        print ("Stop ", str(self.current_time - self.past_time), "sec")

                    self.past_time = self.current_time
                    
                    self.past_time = self.current_time
                    while self.current_time - self.past_time <= 2:
                        self.current_time = rospy.get_time()
                        self.angled = 0
                        self.speed = 5
                        self.drive(self.angled, self.speed)                    
                        print ("After stop, Go ", str(self.current_time - self.past_time), "sec")
                    
                    self.stop = 0
                    self.speed = 1

            # except:
            #     print("Error yellowline")
            
            # Draw Stopline Area x,y
            cv2.rectangle(self.image, (stop_x_min, stop_y_min), (stop_x_max, stop_y_max), (0, 0, 255), 2)
            ###############################################################
            '''
            
            # self.angled = -30
            # self.speed = 0
            # print "Angle : ", self.angled, " Speed : ", self.speed
            # Publish xycar motor & unity motor
            self.drive(self.angled, self.speed)
            self.unitydrive(self.angled, self.speed)
            
            # Check Image
            cv2.imshow("CAM View", self.image)
            cv2.imshow("Line", line_roi)
            cv2.waitKey(1)
            
            
            
if __name__ == '__main__':
    RVS = Robotvisionsystem()

