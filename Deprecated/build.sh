#!/bin/bash

# This is the build script for pkg
mkdir -p build/usr/bin
mkdir -p build/DEBIAN
mkdir -p build/System/Packages
mkdir -p build/Users
mkdir -p build/Volumes
mkdir -p build/Applications

# mkdir -p 'build/System/Packages/base---0.1.0'
# cat >> build/System/Packages/base---0.1.0/pkg-info <<EOF
# InfoType = 1
# [Package]
# Name = "base"
# Version = "0.1.0"
# Architecture = "all"
# Maintainer = "dalixOS Team"
# Description = '''
# A package which is included for all packages
# '''
# Depends = ""
# EOF


chmod +x SysPkgs/pkg/full.py
chmod +x Resources/pkg_lister.py

cp SysPkgs/pkg/full.py build/usr/bin/pkg
cp Resources/pkg_lister.py build/usr/bin/pkg-lister
cp control build/DEBIAN/control

# dpkg -x Resources/bwrap.deb build

dpkg-deb --build build
mv build.deb dalixos-base.deb
mv dalixos-base.deb Resources/

rm -R build