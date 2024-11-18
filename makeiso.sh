#!/bin/bash
shopt -s extglob
set -eu
sudo -v

echo "This script creates disk images for amd64 architecture."
echo "If you need to install for another architecture, then make a github issue for that, and we will look into it."

read -p 'Press [Enter] to continue'

rm -rf disk.img

# 4GB
dd if=/dev/zero of=disk.img bs=4096 count=1048576 status=progress

handle_error() {
	sleep 4
	sudo umount mnt/* || echo ""
	sudo umount mnt || echo ""
	sleep 2
	sudo losetup -d $dev
	sleep 1
	sudo rm -Rf mnt
	exit 0
}

trap handle_error 0

# make neccesary partitions
fdisk disk.img <<EOF
g
n


+512M
t
1

n



w
EOF

chmod +x build.sh
./build.sh

dev="$(sudo losetup -Pf --show disk.img)"

# echo "Please enter your sudo password"
# sudo -k
# sudo -v

sudo mkfs.vfat -F 32 ${dev}p1
sudo mkfs.ext4 ${dev}p2

mkdir -p mnt
sudo mount ${dev}p2 mnt
sudo mkdir mnt/boot
sudo mount ${dev}p1 mnt/boot

# Now we have the file hiearchy in mnt/

# sudo debootstrap unstable mnt http://deb.debian.org/debian/
# Copy base system, and dalixos-base.deb to mnt
sudo rm -Rf base
echo "Extracting base system..."
echo "This may take a while..."
sudo tar -xkf Resources/base.tar.xz
sudo mv base/!(boot) mnt/
sudo mv base/boot/* mnt/boot/
sudo rm -Rf base
ls mnt
sudo cp Resources/dalixos-base.deb mnt/root/dalixos-base.deb


# Preform operations inside chroot
sudo arch-chroot mnt <<EOF
ls root
apt install -y /root/dalixos-base.deb
pkg install --no-deps $(cat Resources/basepkgs.txt)


# ln -sfT / /System/Packages/base/chroot


/sbin/adduser --home /Users/user user <<EOD
1234
1234
User




EOD
passwd <<EOD
1234
1234
EOD

/sbin/usermod -aG sudo user
dpkg-reconfigure locales

/sbin/grub-install --target=x86_64-efi --efi-directory=/boot --removable
/sbin/grub-mkconfig -o /boot/grub/grub.cfg
# genfstab / -U >> /etc/fstab
EOF

# Generate fstab
sudo bash -c 'Resources/genfstab.py mnt mnt/boot > mnt/etc/fstab'

# Generate base package
# ln -sfT mnt/System/Packages/base\*\*\*0.1.0 mnt/System/Packages/base*
mkdir -p mnt/System/Packages/base---0.1.0/chroot
touch mnt/System/Packages/base---0.1.0/chroot/pkg-info
cat >> mnt/System/Packages/base---0.1.0/chroot/pkg-info <<EOF
InfoType = 1
[Package]
Name = "base"
Version = "0.1.0"
Arch = "amd64"
Maintainer = "dalixOS Team"
Description = '''
The base package for dalixOS
'''
Dependencies = "$(cat Resources/basepkgs.txt)"
EOF
# sudo cp -r mnt/!(System|Users|Volumes|Applications|boot|dev|proc|sys|run) mnt/System/Packages/base\*\*\*0.1.0/chroot/

# sudo arch-chroot mnt <<EOF
# chown -R user:user '/System/Packages/base---0.1.0/chroot'
# EOF

unset nounset
unset errexit
sleep 2
sudo umount mnt/proc
sleep 2
sudo umount mnt/proc

sudo umount mnt/* mnt
# sudo umount mnt || echo ""
sudo losetup -d $dev || echo "Loop device is not around? Ignoring..."
sleep 1
#
sudo rm -Rf mnt || echo "Failiure in removing mnt, see error logs for more details..."
# Clean up afterward
# handle_error()
