from io import BytesIO
from PIL import ImageDraw, ImageFont
from collections import defaultdict
import operator
import logging
import sys
from datetime import datetime
import traceback
import time
import base64
import httplib
import json
import os
import ssl

from backEnd.DataManager import DataManager
from backEnd.ClipManager import ClipManager
from vitaToolbox.loggingUtils.LoggingUtils import VitaLogger
from vitaToolbox.strUtils.EnsureUnicode import ensureUnicode

if sys.platform == 'win32':
    _kObjDb2Path = "c:\\Users\\s.hound\\AppData\\Local\\Sighthound Video\\videos\\objdb2"
    _kClipDb2Path = "c:\\Users\\s.hound\\AppData\\Local\\Sighthound Video\\videos\\clipdb"
    _kVideoPath = "e:\\archive"
else:
    _kObjDb2Path = "/Users/alex/Library/Application Support/Sighthound Video/videos/objdb2"
    _kClipDb2Path = "/Users/alex/Library/Application Support/Sighthound Video/videos/clipdb"
    _kVideoPath = "/Users/alex/Library/Application Support/Sighthound Video/My Videos/archive"

_kCloudToken = "c8n5V5bFSUIM9VNIXS3ey7Rui72jqV5vg6pl"
_kFrameOffset = 2

#===============================================================================
#
#===============================================================================
class TimeframeSearch:
    #===========================================================================
    def __init__(self, logger, offset, cameraFilter=None, outfolder=None):
        self._logger = logger
        self._offset = offset
        self._cameraFilter = None if cameraFilter is None else cameraFilter.lower()
        self._outfolder = outfolder
        self._clipMgr = ClipManager(self._logger)
        self._clipMgr.open(ensureUnicode(_kClipDb2Path))
        self._logger.info("Opened clip db")
        self._dataMgr = DataManager(self._logger, self._clipMgr, _kVideoPath)
        self._dataMgr.open(ensureUnicode(_kObjDb2Path))
        self._logger.info("Opened obj db")

    #===========================================================================
    def search(self, beginTime, endTime):
        # get object ranges
        start = time.time()
        objRangesRes = self._dataMgr.getObjectRangesBetweenTimes(beginTime, endTime)
        objRanges = {key: ((x1,x2),(y1,y2),cam) for (key, ((x1,x2),(y1,y2)), cam) in objRangesRes}
        objs = objRanges.keys()
        objQueryTime = time.time() - start
        self._logger.info("Retrieved %d objects in %d ms" % (len(objs), int(objQueryTime*1000)))

        # get object boxes
        start = time.time()
        boxes = self._dataMgr.getObjectBboxesBetweenTimes(objs, beginTime, endTime)
        sortedBoxes = defaultdict(list)
        filteredBoxes = {}

        # put in object buckets
        for box in boxes:
            sortedBoxes[box[6]].append((box[5], box[0], box[1], box[2], box[3]))

        # Take a limited amount of boxes for each object
        for key in sortedBoxes:
            sortedBoxes[key].sort(key=operator.itemgetter(0))

            # Take first frame (+offset), last frame (-offset), and middle frame
            filteredBoxes[key] = []
            totalBoxesForKey = len(sortedBoxes[key])
            if totalBoxesForKey > self._offset:
                # first frame (+offset)
                filteredBoxes[key].append(sortedBoxes[key][self._offset])

                if totalBoxesForKey > (self._offset+1)*2:
                    # middle frame
                    filteredBoxes[key].append(sortedBoxes[key][totalBoxesForKey/2])

                if totalBoxesForKey > self._offset*2:
                    # last frame (-offset)
                    filteredBoxes[key].append(sortedBoxes[key][-self._offset-1])
            else:
                # too few frames, can't even apply offset, just take the middle one
                filteredBoxes[key].append(sortedBoxes[key][totalBoxesForKey/2])
            filteredBoxes[key].sort(key=operator.itemgetter(0))
        boxQueryTime = time.time() - start
        self._logger.info("Retrieved %d boxes for %d objects in %d ms" % (len(boxes), len(sortedBoxes), int(boxQueryTime*1000)))

        objectInfo = {}
        for key in filteredBoxes:
            objectInfo[key] = ( objRanges[key], filteredBoxes[key] )

        return objectInfo

    #===========================================================================
    def getImage(self, id, object, item):
        camera = object[0][2]
        box = object[1][item]
        timestamp = box[0]
        coord = (box[1], box[2], box[3], box[4])
        self._logger.debug("Processing item %d for object %d of camera %s. ts=%d, coord=%s" % \
                       (item, id, camera, timestamp, str(coord)) )

        # Setup the video
        self._dataMgr.setupMarkedVideo(camera, timestamp, timestamp, timestamp)

        # Retrieve the frame
        useTolerance  = True
        wantProcSize  = True
        markupObjList = None
        frame, ms, size = self._dataMgr.getSingleFrame(
                                    camera, timestamp, (0,0), useTolerance,
                                    wantProcSize, markupObjList)
        if frame is None:
            self._logger.error("Could not get frame for ts=%d in %s" % (timestamp, camera))
        else:
            self._logger.debug("Got frame for ts=%d in %s .. procSize=%s, actualMs=%d" % (timestamp, camera, str(size), ms))
        return frame

    #===========================================================================
    def _cloudCallDetections(self, conn, params, headers, image):
        output = []
        conn.request("POST", "/v1/detections?type=face,person&faceOption=landmark,gender", params, headers)
        response = conn.getresponse()
        if response.status == 200:
            result = response.read()
            jsonResult = json.loads(result)
            objects = jsonResult.get("objects", None)
            for x in objects:
                type = x["type"]
                box = x["boundingBox"]
                boxTuple = (box["x"], box["y"], box["width"], box["height"])
                self._logger.debug( "Detection Results: " + type + " at " + str(boxTuple) )
                output.append( type )
                if self._outfolder is not None:
                    color=(255,0,0)
                    if type == "face":
                        color=(255,255,0)
                    if type == "person":
                        color=(0,255,255)

                    draw = ImageDraw.Draw(image)
                    draw.rectangle((boxTuple[0], boxTuple[1], boxTuple[2]+boxTuple[0]-1, boxTuple[3]+boxTuple[1]-1), outline=color)
        else:
            self._logger.error("Error %d in detections: reason=%s msg=%s" % (response.status, response.reason, response.msg))
            output = [ "error" ]
        return output

    #===========================================================================
    def _recognitionBbToTuple(self, box):
        res = [-1, -1, -1, -1]

        for v in box["vertices"]:
            intX = int(v["x"])
            intY = int(v["y"])
            if intX < res[0] or res[0] < 0:
                res[0] = intX
            if intX > res[2] or res[2] < 0:
                res[2] = intX
            if intY < res[1] or res[1] < 0:
                res[1] = intY
            if intY > res[3] or res[3] < 0:
                res[3] = intY

        res[2] = res[2]-res[0]
        res[3] = res[3]-res[1]
        return res


    #===========================================================================
    def _cloudCallRecognitions(self, conn, params, headers, image):
        output = []
        conn.request("POST", "/v1/recognition?objectType=vehicle,licenseplate", params, headers)
        response = conn.getresponse()
        if response.status == 200:
            result = response.read()
            jsonResult = json.loads(result)
            objects = jsonResult.get("objects", [])
            index = 0
            for x in objects:
                index = index + 1
                annotation  = x["vehicleAnnotation"]
                objType     = x["objectType"]
                print "Processing object" + objType
                box         = annotation["bounding"]
                boxTuple = self._recognitionBbToTuple(box)
                confidence  = annotation["recognitionConfidence"]
                license     = annotation.get("licenseplate", None)
                attributes  = annotation["attributes"]["system"]
                make        = attributes["make"]["name"]
                model       = attributes["model"]["name"]
                color       = attributes["color"]["name"]
                objStr      = "[" + objType + "," + make + "," + model + "," + color + ",(" + str(confidence) + ")]"
                if license is not None:
                    boxLp = license["attributes"]["system"]["bounding"]
                    regionLp = license["attributes"]["system"]["region"]["name"]
                    stringLp = license["attributes"]["system"]["string"]["name"]
                    objStr = objStr + "[" + regionLp + "," + stringLp + "]"
                    lpBoxTuple = self._recognitionBbToTuple(boxLp)
                if self._outfolder is not None:
                    draw = ImageDraw.Draw(image)
                    color=(255,128,(index*20)%255)
                    draw.rectangle((boxTuple[0], boxTuple[1], boxTuple[2]+boxTuple[0]-1, boxTuple[3]+boxTuple[1]-1), outline=color)
                    font = ImageFont.truetype('arial.ttf', 10)
                    draw.text((boxTuple[0]+2, boxTuple[1]+2), objStr, font=font, fill=(255,255,255,255))
                    if license is not None:
                        draw.rectangle((lpBoxTuple[0], lpBoxTuple[1], lpBoxTuple[2]+lpBoxTuple[0]-1, lpBoxTuple[3]+lpBoxTuple[1]-1), outline=color)
                output.append(objStr)
        else:
            self._logger.error("Error %d in recognition: reason=%s msg=%s" % (response.status, response.reason, response.msg))
            output = ["error"]
        return output

    #===========================================================================
    def cloudCall(self, image, name):
        output = []
        headers = {"Content-type": "application/json", "X-Access-Token": _kCloudToken}
        conn = httplib.HTTPSConnection("dev.sighthoundapi.com",
            context=ssl.SSLContext(ssl.PROTOCOL_TLSv1))

        with BytesIO() as f:
            image.save(f, format='JPEG')
            image_data= base64.b64encode(f.getvalue())

        params = json.dumps({"image": image_data})
        start = time.time()
        output1 = self._cloudCallDetections(conn, params, headers, image)
        detCallTime = int((time.time() - start)*1000)
        start = time.time()
        output2 = self._cloudCallRecognitions(conn, params, headers, image)
        recCallTime = int((time.time() - start)*1000)

        output1.extend(output2)

        output = "[r=" + str(recCallTime) + "][d=" + str(detCallTime) + "] " + ','.join(output1)

        # only save the image if so requested, and if any objects were found
        if self._outfolder is not None and len(output1) > 0:
            outfile = os.path.join(self._outfolder, name+".jpg")
            image.save(outfile)
        return output

    #===========================================================================
    def processObject(self, key, object):
        itemNo = 1 if len(object[1]) > 2 else 0
        camera = object[0][2]
        timestamp = object[1][itemNo][0]
        if self._cameraFilter is not None and \
           not camera.lower().startswith(self._cameraFilter):
           return None
        self._logger.debug("Processing object " + str(object))
        start = time.time()
        img = self.getImage(key, object, itemNo)
        acqCallTime = int((time.time()-start)*1000)
        if img is not None:
            try:
                name = str(timestamp)+"-"+str(key)+"-"+str(itemNo)
                if self._outfolder is not None:
                    outfile = os.path.join( self._outfolder, name+"-src.jpg")
                    img.save(outfile)
                output = self.cloudCall(img, name)
                self._logger.info("%d in %s: [a=%d]%s" % (timestamp, camera, acqCallTime, output))
            except KeyboardInterrupt:
                raise
            except:
                self._logger.error(traceback.format_exc())
        return None

#===========================================================================
def _setupLogger(verbose):
    # create logger with 'spam_application'
    logger = VitaLogger('TimeframeSearch')
    logger.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(ch)
    return logger

#===========================================================================
def _getopts(argv):
    opts = {}  # Empty dictionary to store key-value pairs.
    while argv:  # While there are arguments left to parse...
        if argv[0][0] == '-':  # Found a "-name value" pair.
            opts[argv[0]] = argv[1] if len(argv) > 1 else "" # Add key and value to the dictionary.
        argv = argv[1:]  # Reduce the argument list by copying it starting from index 1.
    return opts

#===========================================================================
def _printUsage():
    print "Usage ./TimeframeSearch.py -d [YYYYMMDD] [-o outfolder] [-f cameraNameFilter] [-v]"

#===========================================================================
def main():
    args = _getopts(sys.argv)

    dateStr = args.get("-d", None)
    verbose = args.get("-v", False)
    outfolder = args.get("-o", None)
    cameraFilter = args.get("-f", None)

    if dateStr is None:
        _printUsage()
        return -1

    _logger = _setupLogger(verbose)
    try:
        # Figure out start/stop time from the parameter
        date = datetime.strptime(dateStr, '%Y%m%d')
        startEpoch = int((date - datetime(1970,1,1)).total_seconds()*1000)
        stopEpoch = startEpoch + 24*60*60*1000 - 1
        _logger.info("%s => %d,%d" % (dateStr, startEpoch, stopEpoch))

        # Construct and run search
        search = TimeframeSearch(_logger, _kFrameOffset, cameraFilter, outfolder)
        objectInfo = search.search(startEpoch, stopEpoch)

        for key in objectInfo:
            search.processObject(key, objectInfo[key])
    except:
        _logger.error(traceback.format_exc())

#===========================================================================
if __name__ == "__main__":
    main()