#!/bin/bash

# Print commands and exit on errors
set -xe

apt-get update

KERNEL=$(uname -r)
DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" upgrade
apt-get install -y --no-install-recommends \
  autoconf \
  automake \
  bison \
  build-essential \
  ca-certificates \
  cmake \
  cpp \
  curl \
  flex \
  git \
  libboost-dev \
  libboost-filesystem-dev \
  libboost-iostreams1.58-dev \
  libboost-program-options-dev \
  libboost-system-dev \
  libboost-test-dev \
  libboost-thread-dev \
  libc6-dev \
  libevent-dev \
  libffi-dev \
  libfl-dev \
  libgc-dev \
  libgc1c2 \
  libgflags-dev \
  libgmp-dev \
  libgmp10 \
  libgmpxx4ldbl \
  libjudy-dev \
  libpcap-dev \
  libreadline6 \
  libreadline6-dev \
  libssl-dev \
  libtool \
  linux-headers-$KERNEL\
  make \
  mktemp \
  pkg-config \
  python \
  python-dev \
  python-ipaddr \
  python-pip \
  python-psutil \
  python-scapy \
  python-setuptools \
  tcpdump \
  unzip \
  vim \
  wget \
  xcscope-el \
  tcpreplay \
  tmux \
  xterm \
  htop \
  iperf \
  iperf3

# --- Python Pip --- #
curl https://files.pythonhosted.org/packages/53/7f/55721ad0501a9076dbc354cc8c63ffc2d6f1ef360f49ad0fbcce19d68538/pip-20.3.4.tar.gz -o pip-20.3.4.tar.gz
tar -xf pip-20.3.4.tar.gz
cd pip-20.3.4
python setup.py build
python setup.py install

# --- TMUX --- #
cd ..
git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
cat tmuxconf > ~/.tmux.conf
echo "Press prefix + I when starting tmux for the first time to install plugins."