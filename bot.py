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

from boto.s3.connection import S3Connection
from boto.s3.key import Key

try:
    from keys import *
except ImportError:
    raise Exception("You need to define your keys in keys.py")

HAAR_FACE = "/usr/share/opencv/haarcascades/haarcascade_frontalface_alt.xml"
WORKERS = 3

TWITTER_AUTH = OAuth1(  CONSUMER_KEY,
                        CONSUMER_SECRET,
                        ACCESS_TOKEN,
                        ACCESS_TOKEN_SECRET)

TUMBLR_AUTH = OAuth1(   TUMBLR_CONSUMER_KEY,
                        TUMBLR_CONSUMER_SECRET,
                        TUMBLR_ACCESS_TOKEN,
                        TUMBLR_ACCESS_TOKEN_SECRET)

S3 = S3Connection(S3_KEY, S3_SECRET)
S3_BUCKET = S3.get_bucket('busitizer')


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

            if 'retweeted_status' in item:
                continue

            if item['user']['friends_count'] == 0:
                ratio = item['user']['followers_count'] / 1
            else:
                ratio = item['user']['followers_count'] / (item['user']['friends_count'] or 1)
            
            if item['user']['followers_count'] < 3000 or ratio < 10:
                # Let's target more "important" users, or very occassionally, just anyone.
                if random.random() > .001:
                    continue

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

                            s3_key = Key(S3_BUCKET)
                            s3_key.key = os.path.basename(output_path)
                            s3_key.set_contents_from_filename(output_path)
                            s3_key.set_acl('public-read')

                            oembed_params = {
                                'id': item['id_str'],
                                'omit_script': 'true',
                                'hide_thread': 'true'
                            }
                            oembed_request = requests.get("https://api.twitter.com/1.1/statuses/oembed.json", params=oembed_params, auth=TWITTER_AUTH)
                            tweet_html = oembed_request.json()['html']

                            tumblr_data = {
                                "type": "photo",
                                "caption": tweet_html,
                                "source": "http://busitizer.s3.amazonaws.com/%s" % os.path.basename(output_path)
                            }

                            tumblr_response = requests.post("http://api.tumblr.com/v2/blog/busitizer.tumblr.com/post", data=tumblr_data, auth=TUMBLR_AUTH)

                        os.remove(temp_path)



queue = Queue.Queue()

for i in range(WORKERS):
    Worker(queue).start()


r = requests.get("https://stream.twitter.com/1.1/statuses/sample.json", auth=TWITTER_AUTH, stream=True)

for line in r.iter_lines():
    try:
        tweet = json.loads(line)
        if tweet.get('entities', {}).get('media'):
            queue.put(tweet)
    except ValueError as e:
        print("Couldn't parse: %s" % line)

