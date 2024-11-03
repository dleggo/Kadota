#!/bin/python3

import os
from tempfile import TemporaryDirectory
import tomllib

def get_pkg_info(path: str) -> dict:
	assert os.path.exists(path), "Package not found!"
	assert os.path.exist(path + "/pkg-info") # FIXME
	with open(path + "/pkg-info", "rb") as f:
		info = tomllib.load(f)
	return info

def get_deb_info(path: str) -> dict:
	assert os.path.exists(path), "Supplied path does not exist!"
	with TemporaryDirectory() as tmpdir:
		os.system(f"dpkg-deb -R {path} {tmpdir}")
		assert os.path.exists(tmpdir + "/DEBIAN/control"), "No control file found in package!"
		info_list = [] # contains tuples of (key: str, value: str)
		with open(tmpdir + "/DEBIAN/control") as control:
			f = control.read().rstrip()
			a = f.split("\n")
			for b in a:
				if b[0] == " " or b[0] == "\t":
					if info_list:
						info_list[-1] = (info_list[-1][0], info_list[-1][1] + b)
					else:
						raise ValueError("Invalid control file in package!")
				else:
					c = b.split(":")
					assert len(c) == 2, "Invalid control file in package!"
					key,value = c[0], c[1]
					key = key.lstrip().rstrip()
					value = value.lstrip().rstrip()
					info_list.append((key, value))
	info = {}
	for a in info_list:
		info[a[0]] = a[1]
	return info

# path should point to a .deb file
def install_deb(path: str, root: str):
	assert os.path.exists(path), "Supplied path does not exist!"
	assert path.lower()[-4:] == ".deb", "Path does not point to a .deb file!"
	# create pkg directory
	with TemporaryDirectory() as tmpdir:
		# extract pkg
		os.system(f"dpkg -x {path} {tmpdir}")
		# extract metadata
		info = get_deb_info(path)
		print(info)

if __name__ == "__main__":
	install_deb("/home/derek/Code/Dalix/Resources/bwrap.deb", "/home/derek/Code/Dalix/Tests")