import numpy as np
import io
import os
#import rosbag
from PIL import Image
import cv2
from typing import Any
import torchvision.transforms.functional as TF

from pathlib import Path
from rosbags.highlevel import AnyReader

"""


# create reader instance and open for reading
with AnyReader([Path('/home/ros/rosbag_2020_03_24')]) as reader:
    connections = [x for x in reader.connections if x.topic == '/imu_raw/Imu']
    for connection, timestamp, rawdata in reader.messages(connections=connections):
         msg = reader.deserialize(rawdata, connection.msgtype)
         print(msg.header.frame_id)

"""

IMAGE_SIZE = (160, 120)
IMAGE_ASPECT_RATIO = 4 / 3


def process_images(im_list: list, img_process_func) -> list:
    """
    Process image data from a topic that publishes ros images into a list of PIL images
    """
    images = []
    for img_msg in im_list:
        img = img_process_func(img_msg)
        images.append(img)
    return images


def process_tartan_img(msg) -> Image:
    """
    Process image data from a topic that publishes sensor_msgs/Image to a PIL image for the tartan_drive dataset
    """
    img = ros_to_numpy(msg, output_resolution=IMAGE_SIZE) * 255
    img = img.astype(np.uint8)
    # reverse the axis order to get the image in the right orientation
    img = np.moveaxis(img, 0, -1)
    # convert rgb to bgr
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    img = Image.fromarray(img)
    return img


def process_scand_img(msg) -> Image:
    """
    Process image data from a topic that publishes sensor_msgs/CompressedImage to a PIL image for the scand dataset
    """
    # convert sensor_msgs/CompressedImage to PIL image
    img = Image.open(io.BytesIO(msg.data))
    # center crop image to 4:3 aspect ratio
    w, h = img.size
    img = TF.center_crop(
        img, (h, int(h * IMAGE_ASPECT_RATIO))
    )  # crop to the right ratio
    viz_img = TF.resize(img, IMAGE_SIZE)
    # resize image to IMAGE_SIZE
    img = img.resize(IMAGE_SIZE)
    return img


############## Add custom image processing functions here #############


#######################################################################


def process_odom(
    odom_list: list,
    odom_process_func: Any,
    ang_offset: float = 0.0,
) -> dict[np.ndarray, np.ndarray]:
    """
    Process odom data from a topic that publishes nav_msgs/Odometry into position and yaw
    """
    xys = []
    yaws = []
    for odom_msg in odom_list:
        xy, yaw = odom_process_func(odom_msg, ang_offset)
        xys.append(xy)
        yaws.append(yaw)
    return {"position": np.array(xys), "yaw": np.array(yaws)}


def nav_to_xy_yaw(odom_msg, ang_offset: float) -> tuple[list[float], float]:
    """
    Process odom data from a topic that publishes nav_msgs/Odometry into position
    """

    position = odom_msg.pose.pose.position
    orientation = odom_msg.pose.pose.orientation
    yaw = (
        quat_to_yaw(orientation.x, orientation.y, orientation.z, orientation.w)
        + ang_offset
    )
    return [position.x, position.y], yaw


############ Add custom odometry processing functions here ############


#######################################################################


# def get_images_and_odom(
#     bag: rosbag.Bag,
#     imtopics: list[str] or str,
#     odomtopics: list[str] or str,
#     img_process_func: Any,
#     odom_process_func: Any,
#     rate: float = 4.0,
#     ang_offset: float = 0.0,
# ):
#     """
#     Get image and odom data from a bag file

#     Args:
#         bag (rosbag.Bag): bag file
#         imtopics (list[str] or str): topic name(s) for image data
#         odomtopics (list[str] or str): topic name(s) for odom data
#         img_process_func (Any): function to process image data
#         odom_process_func (Any): function to process odom data
#         rate (float, optional): rate to sample data. Defaults to 4.0.
#         ang_offset (float, optional): angle offset to add to odom data. Defaults to 0.0.
#     Returns:
#         img_data (list): list of PIL images
#         traj_data (list): list of odom data
#     """
#     # check if bag has both topics
#     odomtopic = None
#     imtopic = None
#     if type(imtopics) == str:
#         imtopic = imtopics
#     else:
#         for imt in imtopics:
#             if bag.get_message_count(imt) > 0:
#                 imtopic = imt
#                 break
#     if type(odomtopics) == str:
#         odomtopic = odomtopics
#     else:
#         for ot in odomtopics:
#             if bag.get_message_count(ot) > 0:
#                 odomtopic = ot
#                 break
#     if not (imtopic and odomtopic):
#         # bag doesn't have both topics
#         return None, None

#     synced_imdata = []
#     synced_odomdata = []
#     # get start time of bag in seconds
#     currtime = bag.get_start_time()
#     starttime = currtime

#     curr_imdata = None
#     curr_odomdata = None
#     times = []

#     for topic, msg, t in bag.read_messages(topics=[imtopic, odomtopic]):
#         if topic == imtopic:
#             curr_imdata = msg
#         elif topic == odomtopic:
#             curr_odomdata = msg
#         if (t.to_sec() - currtime) >= 1.0 / rate:
#             if curr_imdata is not None and curr_odomdata is not None:
#                 synced_imdata.append(curr_imdata)
#                 synced_odomdata.append(curr_odomdata)
#             currtime = t.to_sec()
#             times.append(currtime - starttime)

#     img_data = process_images(synced_imdata, img_process_func)
#     traj_data = process_odom(
#         synced_odomdata,
#         odom_process_func,
#         ang_offset=ang_offset,
#     )

#     return img_data, traj_data

def get_images_and_odom(
    dir: str,
    imtopic: str,
    odomtopic: str,
    img_process_func: Any,
    odom_process_func: Any,
    rate: float = 4.0,
    ang_offset: float = 0.0,
):
    """
    Get image and odom data from a bag file

    Args:
        dir : rosbag2 directory
        imtopic : topic name for image data
        odomtopic : topic name for odom data
        img_process_func (Any): function to process image data
        odom_process_func (Any): function to process odom data
        rate (float, optional): rate to sample data. Defaults to 4.0.
        ang_offset (float, optional): angle offset to add to odom data. Defaults to 0.0.
    Returns:
        img_data (list): list of PIL images
        traj_data (list): list of odom data
    """
    # # check if bag has both topics
    # odomtopic = None
    # imtopic = None
    # if type(imtopics) == str:
    #     imtopic = imtopics
    # else:
    #     for imt in imtopics:
    #         if bag.get_message_count(imt) > 0:
    #             imtopic = imt
    #             break
    # if type(odomtopics) == str:
    #     odomtopic = odomtopics
    # else:
    #     for ot in odomtopics:
    #         if bag.get_message_count(ot) > 0:
    #             odomtopic = ot
    #             break
    if not (imtopic and odomtopic):
        # bag doesn't have both topics
        return None, None

    # read ros2bag
    img_raw_data = []
    odom_data = []
    with AnyReader([Path(dir)]) as reader:
        img_connections = [x for x in reader.connections if x.topic == imtopic]
        odom_connections = [x for x in reader.connections if x.topic == odomtopic]
        #print(img_connections)
        #print(odom_connections)
        for connection, timestamp, rawdata in reader.messages(connections=img_connections):
            msg = reader.deserialize(rawdata, connection.msgtype)
            img_raw_data.append(msg)
        for connection, timestamp, rawdata in reader.messages(connections=odom_connections):
            msg = reader.deserialize(rawdata, connection.msgtype)
            odom_data.append(msg)

    for i in range(0, len(img_raw_data)):
        print(img_raw_data[i])
    for i in range(0, len(odom_data)):
        print(odom_data[i])

    img_data = []
    traj_data = []
    # synced_imdata = []
    # synced_odomdata = []
    # # get start time of bag in seconds
    # currtime = bag.get_start_time()
    # starttime = currtime

    # curr_imdata = None
    # curr_odomdata = None
    # times = []

    # for topic, msg, t in bag.read_messages(topics=[imtopic, odomtopic]):
    #     if topic == imtopic:
    #         curr_imdata = msg
    #     elif topic == odomtopic:
    #         curr_odomdata = msg
    #     if (t.to_sec() - currtime) >= 1.0 / rate:
    #         if curr_imdata is not None and curr_odomdata is not None:
    #             synced_imdata.append(curr_imdata)
    #             synced_odomdata.append(curr_odomdata)
    #         currtime = t.to_sec()
    #         times.append(currtime - starttime)

    # img_data = process_images(synced_imdata, img_process_func)
    # traj_data = process_odom(
    #     synced_odomdata,
    #     odom_process_func,
    #     ang_offset=ang_offset,
    # )

    return img_data, traj_data

def is_backwards(
    pos1: np.ndarray, yaw1: float, pos2: np.ndarray, eps: float = 1e-5
) -> bool:
    """
    Check if the trajectory is going backwards given the position and yaw of two points
    Args:
        pos1: position of the first point

    """
    dx, dy = pos2 - pos1
    return dx * np.cos(yaw1) + dy * np.sin(yaw1) < eps


# cut out non-positive velocity segments of the trajectory
def filter_backwards(
    img_list: list[Image.Image],
    traj_data: dict[np.ndarray],
    start_slack: int = 0,
    end_slack: int = 0,
) -> tuple[list[np.ndarray], list[int]]:
    """
    Cut out non-positive velocity segments of the trajectory
    Args:
        traj_type: type of trajectory to cut
        img_list: list of images
        traj_data: dictionary of position and yaw data
        start_slack: number of points to ignore at the start of the trajectory
        end_slack: number of points to ignore at the end of the trajectory
    Returns:
        cut_trajs: list of cut trajectories
        start_times: list of start times of the cut trajectories
    """
    traj_pos = traj_data["position"]
    traj_yaws = traj_data["yaw"]
    cut_trajs = []
    start = True

    def process_pair(traj_pair: list) -> tuple[list, dict]:
        new_img_list, new_traj_data = zip(*traj_pair)
        new_traj_data = np.array(new_traj_data)
        new_traj_pos = new_traj_data[:, :2]
        new_traj_yaws = new_traj_data[:, 2]
        return (new_img_list, {"position": new_traj_pos, "yaw": new_traj_yaws})

    for i in range(max(start_slack, 1), len(traj_pos) - end_slack):
        pos1 = traj_pos[i - 1]
        yaw1 = traj_yaws[i - 1]
        pos2 = traj_pos[i]
        if not is_backwards(pos1, yaw1, pos2):
            if start:
                new_traj_pairs = [
                    (img_list[i - 1], [*traj_pos[i - 1], traj_yaws[i - 1]])
                ]
                start = False
            elif i == len(traj_pos) - end_slack - 1:
                cut_trajs.append(process_pair(new_traj_pairs))
            else:
                new_traj_pairs.append(
                    (img_list[i - 1], [*traj_pos[i - 1], traj_yaws[i - 1]])
                )
        elif not start:
            cut_trajs.append(process_pair(new_traj_pairs))
            start = True
    return cut_trajs


def quat_to_yaw(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    w: np.ndarray,
) -> np.ndarray:
    """
    Convert a batch quaternion into a yaw angle
    yaw is rotation around z in radians (counterclockwise)
    """
    t3 = 2.0 * (w * z + x * y)
    t4 = 1.0 - 2.0 * (y * y + z * z)
    yaw = np.arctan2(t3, t4)
    return yaw


def ros_to_numpy(
    msg, nchannels=3, empty_value=None, output_resolution=None, aggregate="none"
):
    """
    Convert a ROS image message to a numpy array
    """
    if output_resolution is None:
        output_resolution = (msg.width, msg.height)

    is_rgb = "8" in msg.encoding
    if is_rgb:
        data = np.frombuffer(msg.data, dtype=np.uint8).copy()
    else:
        data = np.frombuffer(msg.data, dtype=np.float32).copy()

    data = data.reshape(msg.height, msg.width, nchannels)

    if empty_value:
        mask = np.isclose(abs(data), empty_value)
        fill_value = np.percentile(data[~mask], 99)
        data[mask] = fill_value

    data = cv2.resize(
        data,
        dsize=(output_resolution[0], output_resolution[1]),
        interpolation=cv2.INTER_AREA,
    )

    if aggregate == "littleendian":
        data = sum([data[:, :, i] * (256**i) for i in range(nchannels)])
    elif aggregate == "bigendian":
        data = sum([data[:, :, -(i + 1)] * (256**i) for i in range(nchannels)])

    if len(data.shape) == 2:
        data = np.expand_dims(data, axis=0)
    else:
        data = np.moveaxis(data, 2, 0)  # Switch to channels-first

    if is_rgb:
        data = data.astype(np.float32) / (
            255.0 if aggregate == "none" else 255.0**nchannels
        )

    return data
