# AIRSEAI Full Local Deployment Guide (for Jetson AGX Orin)

## System Requirements

- **Hardware**: Nvidia Jetson AGX Orin
- **Operating System**: JetPack 6.0 (based on Ubuntu 22.04), bundled with CUDA 12.2 For more details, please refer to the official [NVIDIA JetPack 6.0 documentation](https://docs.nvidia.com/jetson/archives/jetpack-archived/jetpack-60/index.html).

- **Python**: Use Python 3.10 across all environments (use conda to manage environment-specific versions)

------

## Source Code Acquisition

Flash the device using NVIDIA's official tools, select JetPack 6.0 (based on Ubuntu 22.04) using [NVIDIA SDK Manager](https://developer.nvidia.com/sdk-manager).

> ⚠️ Important: The username must be set to:

```
airsbot2
```

Otherwise, some paths in AIRSEAI packages may not align, causing debugging issues.

After flashing, run:

```
sudo apt-get update
sudo apt-get upgrade
```

Create the main project folder:

```
mkdir ~/airseai
```

Add the following to the end of your `.bashrc` and source it:

```
export DIR_AIRSEAI=$HOME/airseai
source ~/.bashrc
```

Clone the source code:

```
cd ~/airseai
mkdir src
cd src
git clone https://github.com/airs-cuhk/airseai.git
```

------

## Installing ROS2 Humble

Run the installation script:

```
bash ~/airseai/src/airseai/scripts/software_setup/install_ros_humble.sh
```

Then source the environment and add it to `.bashrc`:

```
source /opt/ros/humble/setup.bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
```

> ⚠️ Tip: Installation errors are often caused by network issues. Carefully check the logs.

------


## Module Installation

### Install Conda

```
wget http://repo.continuum.io/miniconda/Miniconda3-py39_4.9.2-Linux-aarch64.sh
bash Miniconda3-py39_4.9.2-Linux-aarch64.sh
```

Set the installation path to:

```
/home/airsbot2/miniconda3
```

------

### Install Dependencies

```
sudo pip install vcstool
cd ${DIR_AIRSEAI}/src
vcs-import < airseai/dependencies.yaml
sudo apt install libcudnn8 libcudnn8-dev
```

------

### AIRSEAI Perception Module

```
conda create -n airseai_perception python=3.10
conda activate airseai_perception
```

Install PyTorch (for JetPack 6.0):

```
wget https://download.pytorch.org/whl/torch-2.3.0-cp310-cp310-linux_aarch64.whl
wget https://download.pytorch.org/whl/torchaudio-2.3.0+952ea74-cp310-cp310-linux_aarch64.whl
wget https://download.pytorch.org/whl/torchvision-0.18.0a0+6043bc2-cp310-cp310-linux_aarch64.whl

pip install torch*.whl torchaudio*.whl torchvision*.whl
```

Install perception libraries:

```
cp -r ${DIR_AIRSEAI}/src/Grounded-Segment-Anything/* ${DIR_AIRSEAI}/src/airseai/airseai_perception/lib/
cd ${DIR_AIRSEAI}/src/airseai/airseai_perception/lib/
pip install --no-build-isolation -e GroundingDINO
pip install -e segment-anything
pip install --upgrade diffusers[torch]
pip install -r requirements.txt
pip install --upgrade transformers
```

Download pretrained weights:

```
cd models
git lfs install
GIT_LFS_SKIP_SMUDGE=1 git clone https://hf-mirror.com/google-bert/bert-base-uncased
cd bert-base-uncased && git lfs pull && cd ..
wget https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth
wget https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth
```

Build the module:

```
cd ${DIR_AIRSEAI}
conda activate airseai_perception
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release --symlink-install --packages-up-to airseai_perception
```

------

### AIRSEAI Grasp Module

```
conda create -n airseai_grasp python=3.10.12
conda activate airseai_grasp
```

Install PyTorch:

```
pip install torch-2.3.0-cp310-cp310-linux_aarch64.whl
pip install torchaudio-2.3.0+952ea74-cp310-cp310-linux_aarch64.whl
pip install torchvision-0.18.0a0+6043bc2-cp310-cp310-linux_aarch64.whl
```

Install Realsense SDK:

```
sudo apt install ros-humble-librealsense2*
sudo apt install ros-humble-realsense2-*
```

Download & configure Scale-Balanced-Grasp:

```
cd ${DIR_AIRSEAI}/src/airseai/airseai_grasp/lib
git clone https://github.com/mahaoxiang822/Scale-Balanced-Grasp
mv Scale-Balanced-Grasp Scale_Balanced_Grasp
cd Scale_Balanced_Grasp
cp ${DIR_AIRSEAI}/src/airseai/airseai_grasp/doc/3rd_party/requirements.txt requirements.txt
pip install -r requirements.txt
```

Download & extract tolerance labels:

```
mkdir logs
mv tolerance.tar logs/
cd logs
tar -xvf tolerance.tar
```

Install PointNet2, KNN, GraspNet API:

```
cd pointnet2
pip install .

cd ../knn
cp ${DIR_AIRSEAI}/src/airseai/airseai_grasp/doc/3rd_party/knn.h src/knn.h 
cp ${DIR_AIRSEAI}/src/airseai/airseai_grasp/doc/3rd_party/vision.h src/cuda/vision.h
pip install .

cd ..
git clone https://github.com/graspnet/graspnetAPI
cd graspnetAPI
cp ${DIR_AIRSEAI}/src/airseai/airseai_grasp/doc/3rd_party/setup.py setup.py
pip install .
```

Build Grasp Module:

```
cd ${DIR_AIRSEAI}
conda activate airseai_grasp
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release --symlink-install --packages-up-to airseai_grasp
```

------

### Navigation & Planner (Base Environment)

Deactivate conda:

```
conda deactivate
```

Install dependencies:

```
sudo apt install ros-humble-nav2-core ros-humble-pcl-ros libasound-dev portaudio19-dev libportaudio2 libportaudiocpp0
pip install pyaudio openai pocketsphinx open3d
sudo apt install ros-humble-cartographer ros-humble-cartographer-ros
sudo apt install ros-humble-nav2-simple-commander ros-humble-navigation2
sudo apt install ros-humble-pointcloud-to-laserscan ros-humble-tf-transformations
sudo apt install libopenblas-dev
```

Build AIRSEAI base modules:

```
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release --symlink-install --packages-up-to neo_local_planner2 airseai_chat airseai_description airseai_interface airseai_localization airseai_navigation airseai_object airseai_planner
```

Rebuild in corresponding environments:

```
conda activate airseai_perception
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release --symlink-install --packages-up-to airseai_perception

conda activate airseai_grasp
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release --symlink-install --packages-up-to airseai_grasp
```

------

## Module Launching

```
# Localization & Navigation
ros2 launch airseai_localization airseai_localization_gt_sim.launch.py
ros2 launch airseai_navigation airseai_navigation_sim.launch.py
ros2 service call /airseai_navigation/navigate_to_pose airseai_interface/srv/AirseaiNav "{x: 0.5, y: 0.0, theta: 0.0}"

# Perception
conda activate airseai_perception
ros2 launch airseai_perception run_airseai_perception_node.launch.py

# Grasp
conda activate airseai_grasp
ros2 launch airseai_grasp grasp_sim.launch.py use_isaac_sim:=true
ros2 service call /airseai_grasp/grasp_server airseai_interface/srv/AirseaiGrasp "{task: 'pick', obj: 'apple'}"
```

------

## LLM Integration (ChatGPT API)

Edit `airseai_planner/config/airseai_planner.yaml`:

```
semantic_map_file: "nav_goal.yaml"
llm_server_url: "https://your-llm-server/api/chat"
openai_api_key: "your-key"
openai_api_url: "https://pro.aiskt.com/v1"
```

Launch planner:

```
cd ${DIR_AIRSEAI}
source install/local_setup.bash
ros2 launch airseai_planner airseai_planner_launch.py
```

Test example:

```
ros2 service call /airseai_planner/planner_server airseai_interface/srv/AirseaiInstruct "msg: Go to the table and pick up the sugar box"
```

And the it will output the planning results like:

```
[llm_planner-1] [INFO] [1744863322.650317661] [airseai_planner]: Parsing users' instruction: Go to the table and pick up the sugar box
[llm_planner-1] [INFO] [1744863325.287019214] [airseai_planner]: LLM planned task list: [['go_to', ['coordinate table', [1.3103794701759044, 3.852526931762695, 1.5703794701759044]]], ['pick_up', ['sugar box']], ['go_to', ['coordinate table', [1.3103794701759044, 3.852526931762695, 1.5703794701759044]]], ['place', ['sugar box']]]
[llm_planner-1] [INFO] [1744863325.288905759] [airseai_planner]: Start LLM planner scheduling...
```



------

## Connecting to Isaac Sim

Install Isaac Sim 4.2.0 from [NVIDIA's official download page](https://docs.omniverse.nvidia.com/4.5.0/installation/download.html).

### Server Environment for Isaac Sim

The server used to run Isaac Sim is equipped with an Intel Core i5-13600KF CPU with 64GB memory and an NVIDIA RTX 4090 GPU is our environment.

Ensure both Orin and the host have ROS 2 Humble installed.

Verify with:

```
source /opt/ros/humble/setup.bash
printenv | grep ROS
```

> Ensure both devices are in the same local network and share the same `ROS2_DOMAIN_ID`:

```
export ROS_DOMAIN_ID=1
echo $ROS_DOMAIN_ID
```

Test communication:

```
# On host
ros2 run demo_nodes_cpp listener

# On Orin
ros2 run demo_nodes_cpp talker
```

If you see "Hello World" messages arriving on the host, your network setup is successful.

## Testcase & Demo

We provide some simple scripts to run the demo under the path:

```
airseai/scripts/testcase
```

Since different environments are required for certain component, we use TMUX to integrate the windows.

You can install TMUX by:

```
sudo apt install tmux
```

Then you can simple run the demo by:

```
cd airseai/scripts/testcase
./run_isaac.sh
```

It will takes a while to boot up and after that you can type your instruction.

## Jetson Orin – Isaac Sim Environment Setup Q&A


### Q1: Where can I download Isaac Sim? Which version is recommended?

You can download [Isaac Sim 4.2.0](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/download.html) directly from the official NVIDIA Omniverse page. No need for Omniverse Launcher.

---

### Q2: Where is the installation guide?

Follow the workstation installation documentation:  
👉 [Install Workstation — Isaac Sim Docs](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/install_workstation.html)

---

### Q3: Where is the usd file for Isaac simulation?

Under the path:

```bash
airseai_sim/airseai/airsbot2_manipulator_ros2_office.usd
```

---

### Q4: How to verify both machines are on the same network?

1. Run `ifconfig` to check IP addresses.
2. Use `ping`:

```bash
ping <other-machine-IP>
```

Example output:

```
64 bytes from 10.60.2.107: icmp_seq=1 ttl=63 time=11.7 ms
```

---

### Q5: How to set up ROS 2 domain?

On both machines:

```bash
export ROS_DOMAIN_ID=1
echo $ROS_DOMAIN_ID
```

Output should be:

```
1
```

---

### Q6: What if the machines can’t ping each other?

Use `ip route`:

```bash
ip route
```

To assign static IP manually (example):

```bash
sudo ip addr add 192.168.1.100/24 dev eth0
sudo ip route add default via 192.168.1.1
```

---

### Q7: Ping works, but ROS 2 messages don’t arrive?

Check firewall:

```bash
sudo ufw status verbose
sudo ufw disable
```

---

### Q8: How to verify if packets arrive at the NIC?

Example using `tcpdump` on SSH port:

```bash
sudo tcpdump -i eth0 tcp port 22
```

Then test:

```bash
ssh user@192.168.1.100
```

If successful, packets will be logged.

---

### Q9: How to test application-layer UDP?

Create `udp_listener.py`:

```python
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 8888))
print("Listening on port 8888")
while True:
    data, addr = sock.recvfrom(1024)
    print(f"Received from {addr}: {data.decode()}")
```

Run it:

```bash
python3 udp_listener.py
```

From another machine:

```bash
echo "hello" | nc -u <listener-IP> 8888
```

If blocked, disable firewall:

```bash
sudo systemctl stop firewalld
```

---

### Q10: Can not load the airseai model into Isacc Sim correctly?

Some of the simulation resource are online, sometimes it might cause mistake due to the network. You can download the asset and use it locally. The instructions are here [Asset]([Setup FAQ — Isaac Sim Documentation](https://docs.isaacsim.omniverse.nvidia.com/4.2.0/installation/install_faq.html#assets-and-nucleus)).

