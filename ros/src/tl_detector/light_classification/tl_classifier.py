from styx_msgs.msg import TrafficLight
import numpy as np
import os
import six.moves.urllib as urllib
import tarfile
import tensorflow as tf
import zipfile
import cv2
import rospy

from utils import label_map_util
from utils import visualization_utils as vis_util

class TLClassifier(object):
    VISUALIZE = False

    def __init__(self, is_site):
        self.detection_graph = None
        self.detection_boxes = None
        self.detection_scores = None
        self.detection_classes = None
        self.visualize_image = None
        self.is_real = is_site
        self.label_map = None
        self.category_index = None

        if self.is_real:
            MODEL_NAME = 'ssd_inception_v2_coco_ud_capstone_real'
            rospy.loginfo("In real site environment...use {}".format(MODEL_NAME))
        else:
            MODEL_NAME = 'ssd_inception_v2_coco_ud_capstone_sim'
            rospy.loginfo("In simulator environment...use {}".format(MODEL_NAME))

        #CLASSIFIER_BASE = 'light_classification'
        CLASSIFIER_BASE = os.path.dirname(os.path.realpath(__file__))
        PATH_TO_CKPT = CLASSIFIER_BASE + '/' + MODEL_NAME + '/frozen_inference_graph.pb'
        PATH_TO_LABELS = CLASSIFIER_BASE + '/label_map.pbtxt'
        NUM_CLASSES = 4

        """
        #MODEL_FILE = "{}.tar.gz".format(MODEL_NAME)
        #DOWNLOAD_BASE = \
        #    'http://download.tensorflow.org/models/object_detection/'

        # TODO: figure out how we make the models available
        #   Do we store them git repo? or do we upload them
        #   somewhere and have them hosted somewhere(google drive?)?

        ### Download the model file if not already there
        if not os.path.exists(MODEL_FILE):
            print("Downloading {}".format(DOWNLOAD_BASE + MODEL_FILE))
            opener = urllib.request.URLopener()
            opener.retrieve(DOWNLOAD_BASE + MODEL_FILE, MODEL_FILE)
            tar_file = tarfile.open(MODEL_FILE)
            for file in tar_file.getmembers():
                file_name = os.path.basename(file.name)
                if 'frozen_inference_graph.pb' in file_name:
                    tar_file.extract(file, os.getcwd())
        """

        ### Load frozen Tensorflow model graph
        self.detection_graph = tf.Graph()
        with self.detection_graph.as_default():
            od_graph_def = tf.GraphDef()
            with tf.gfile.GFile(PATH_TO_CKPT, 'rb') as fid:
                serialized_graph = fid.read()
                od_graph_def.ParseFromString(serialized_graph)
                tf.import_graph_def(od_graph_def, name='')

        ### Load label map
        self.label_map = label_map_util.load_labelmap(PATH_TO_LABELS)
        categories = label_map_util.convert_label_map_to_categories(self.label_map,
            max_num_classes=NUM_CLASSES, use_display_name=True)
        self.category_index = label_map_util.create_category_index(categories)


    def run_inference_for_single_image(self, image):
        self.detection_boxes = None
        self.detection_scores = None
        self.detection_classes = None

        with self.detection_graph.as_default():
            with tf.Session() as sess:
                # Get handles to input and output tensors
                ops = tf.get_default_graph().get_operations()
                all_tensor_names = \
                    {output.name for op in ops for output in op.outputs}
                tensor_dict = {}
                for key in [
                    'num_detections', 'detection_boxes', 'detection_scores',
                    'detection_classes'
                ]:
                    tensor_name = key + ':0'
                    if tensor_name in all_tensor_names:
                        tensor_dict[key] = \
                            tf.get_default_graph().get_tensor_by_name(tensor_name)

                image_tensor = \
                    tf.get_default_graph().get_tensor_by_name('image_tensor:0')

                ### Run inference
                # Expand dimensions since the model expects
                # images to have shape: [1, None, None, 3]
                image_np_expanded = np.expand_dims(image, axis=0)
                output_dict = sess.run(tensor_dict,
                             feed_dict={image_tensor: image_np_expanded})

                # all outputs are float32 numpy arrays,
                # so convert types as appropriate
                self.detection_boxes = output_dict['detection_boxes'][0]
                self.detection_scores = output_dict['detection_scores'][0]
                self.detection_classes = \
                    output_dict['detection_classes'][0].astype(np.uint8)


    def get_classification(self, image):
        """Determines the color of the traffic light in the image

        Args:
            image (cv::Mat): image containing the traffic light

        Returns:
            int: ID of traffic light color (specified in styx_msgs/TrafficLight)

        """
        image_np = np.asarray(image, dtype="int32")

        ### Detect traffic lights ###
        self.run_inference_for_single_image(image_np)

        # Get the detected box with the highest score over minimum threshold
        MIN_THRESHOLD = 0.50

        max_score_indx = np.argmax(self.detection_scores)
        score = self.detection_scores[max_score_indx]
        clazz = self.detection_classes[max_score_indx]

        if score > MIN_THRESHOLD:

            vis_util.visualize_boxes_and_labels_on_image_array(
                image_np,
                np.squeeze(self.detection_boxes),
                np.squeeze(self.detection_classes).astype(np.int32),
                np.squeeze(self.detection_scores),
                self.category_index,
                use_normalized_coordinates=True,
                min_score_thresh=MIN_THRESHOLD,
                line_thickness=3)

            self.visualize_image = image_np

            if clazz == 1:
                return TrafficLight.GREEN
            elif clazz == 2:
                return TrafficLight.RED
            elif clazz == 3:
                return TrafficLight.YELLOW

        return TrafficLight.UNKNOWN
