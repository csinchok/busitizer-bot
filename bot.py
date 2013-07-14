import json
import threading
import Queue
import tempfile
import StringIO
import os
import random

import cv2
import cv2.cv as cv
import numpy
from PIL import Image

import requests
from requests_oauthlib import OAuth1

HAAR_FACE = "/usr/share/opencv/haarcascades/haarcascade_frontalface_alt.xml"
WORKERS = 3
AUTH = OAuth1(  'D5YcTlIiPqBS2f6vFjvoBw',
                'neyANLWJRrhrYG3RejfADAHslMMHDhOpw4cMZZ4d0XQ',
                '471652063-JjY1SSsmVNWIP58fa9mqcF2ERS6U5IsjT6EOpKk',
                'rTgP3coux1pENBxsX8GM68FnHCFHPrMSO7urDtTcs')

BUSEYS_PATH = os.path.join(os.getcwd(), 'faces')
BUSEYS = [Image.open(os.path.join(BUSEYS_PATH, filename)) for filename in os.listdir(BUSEYS_PATH)]

class Worker(threading.Thread):

    def __init__(self, queue):
        self.__queue = queue
        threading.Thread.__init__(self)

    def run(self):
        while 1:
            item = self.__queue.get()
            if item is None:
                break

            for media in item['entities']['media']:
                if media['type'] == 'photo':
                    fd , temp_path= tempfile.mkstemp()
                    temp_file = os.fdopen(fd, 'wb')
                    r = requests.get(media['media_url'])
                    if r.status_code == 200:
                        for chunk in r.iter_content():
                            temp_file.write(chunk)
                        temp_file.close()

                        img_color = cv2.imread(temp_path)
                        img_gray = cv2.cvtColor(img_color, cv.CV_RGB2GRAY)
                        img_gray = cv2.equalizeHist(img_gray)

                        cascade = cv2.CascadeClassifier(HAAR_FACE)

                        rects = cascade.detectMultiScale(img_gray, scaleFactor=1.3, minNeighbors=4, minSize=(20, 20), flags=cv.CV_HAAR_SCALE_IMAGE)
                        if len(rects) != 0:
                            rects[:, 2:] += rects[:, :2]
                            print("Found face @ %s (%s)" % (rects, media['media_url']))
                            img_out = img_color.copy()

                            original = Image.open(temp_path)
                            
                            for x1, y1, x2, y2 in rects:
                                cv2.rectangle(img_out, (x1, y1), (x2, y2), (0, 255, 0), 2)

                                width = x2 - x1
                                height = y2 - y1

                                overlay = random.choice(BUSEYS).resize((int(width * 1.5), int(height * 1.5)))
                                overlay = overlay.rotate(random.randint(-15,15))
                                if random.random() < 0.5:
                                    overlay = overlay.transpose(Image.FLIP_LEFT_RIGHT)

                                paste_coord = (x1 - (width/6), y1 - (height/3))
                                if overlay.mode == 'RGBA':
                                    original.paste(overlay, paste_coord, mask=overlay)
                                else:
                                    original.paste(overlay, paste_coord)

                            output_fd, output_path = tempfile.mkstemp(suffix=".jpg", dir="/var/busitizer/outputs")
                            original.save(output_path)

                        os.remove(temp_path)



queue = Queue.Queue()

for i in range(WORKERS):
    Worker(queue).start()


r = requests.get("https://stream.twitter.com/1.1/statuses/sample.json", auth=AUTH, stream=True)

for line in r.iter_lines():
    try:
        tweet = json.loads(line)
    except ValueError as e:
        print("Couldn't parse: %s" % line)

    if tweet.get('entities', {}).get('media'):
        queue.put(tweet)

