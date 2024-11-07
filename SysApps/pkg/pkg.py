#!/bin/python3

import os
from tempfile import TemporaryDirectory
import toml
from packaging.version import Version
from collections import namedtuple
import argparse
from distutils.dir_util import copy_tree

pkg_info_t = namedtuple('pkg_info_t', ['name', 'version', 'path'])

root = ""

def get_pkg_info(path: str) -> dict:
	"""
	Reads and returns package metadata from a pkg-info file.

	This function asserts the existence of a package directory and its pkg-info file,
	then loads the metadata from the pkg-info file using the TOML format and returns
	it as a dictionary.

	:param path: The path to the package directory containing the pkg-info file.
	:return: A dictionary containing the package metadata.
	:raises AssertionError: If the package directory or pkg-info file does not exist.
	"""
	assert os.path.exists(path), "Package not found!"
	assert os.path.exist(path + "/pkg-info") # FIXME
	with open(path + "/pkg-info", "r") as f:
		info = toml.load(f)
	return info

def get_deb_info(path: str) -> dict:
	"""
	Extracts metadata from a .deb package.

	This function extracts all the metadata from a .deb package, and returns it as a dictionary.

	:raises ValueError: The package's control file is invalid.
	:raises FileNotFoundError: The package does not exist.
	"""
	assert os.path.exists(path), "Supplied path does not exist!"
	with TemporaryDirectory() as tmpdir:
		os.system(f"dpkg-deb -R {path} {tmpdir}")
		assert os.path.exists(tmpdir + "/DEBIAN/control"), "No control file found in package!"
		info_list = [] # contains tuples of (key: str, value: str)
		with open(tmpdir + "/DEBIAN/control") as control:
			file = control.read().rstrip()
			entry_list = file.split("\n")
			for entry in entry_list:
				if entry[0] == " " or entry[0] == "\t":
					if info_list:
						info_list[-1] = (info_list[-1][0], info_list[-1][1] + "\n"  + entry)
					else:
						raise ValueError("Invalid control file in package!")
				else:
					entry_split = entry.split(":")
					entry_split[1] = ''.join(entry_split[1:])

					key,value = entry_split[0:2]
					key = key.lstrip().rstrip()
					value = value.lstrip().rstrip()
					info_list.append((key, value))
	info = {}
	for entry_list in info_list:
		info[entry_list[0]] = entry_list[1]
	return info

def deb_to_pkg_info(info: dict) -> dict:
	"""
	Convert a debian control file info dict into a dalixOS pkg-info dict.

	This function takes a dict generated by get_deb_info and converts it into a dict
	that can be written to a pkg-info file.

	Raises:
		ValueError: If the control file is invalid
	"""
	pkg_info = {
		"InfoType": 1,
		"Package": {}
	}
	try:
		pkg_info["Package"]["Name"] = info["Package"]
		pkg_info["Package"]["Version"] = info["Version"]
		pkg_info["Package"]["Arch"] = info["Architecture"]
		pkg_info["Package"]["Maintainer"] = info["Maintainer"]
		pkg_info["Package"]["Description"] = info["Description"]
		if "Depends" in info:
			deps = info["Depends"]
			deps = deps.replace(",", "\n").replace("(", "").replace(")", "").replace(" ", "")
			pkg_info["Package"]["Dependencies"] = deps
		else:
			pkg_info["Package"]["Dependencies"] = ""
	except KeyError:
		raise ValueError("Invalid debian control file in package!")
	return pkg_info

def symlink(src: str, dst: str):
	"""
	Creates a symbolic link from src to dst. dst is what gets created.

	Ensures that the directory of dest exists before creating the symlink.
	"""
	os.makedirs(src, exist_ok=True)

	dst_dir = os.path.dirname(dst)
	os.makedirs(dst_dir, exist_ok=True)

	# relative_path = os.path.relpath(source_path, target_dir)
	os.symlink(src, dst, target_is_directory=os.path.isdir(src))


# path should point to a .deb file
def install_deb(path: str):
	"""
	Installs a .deb package into the system.

	This function will install a .deb package into the system. The package will be extracted and
	installed into a directory under /System/Packages, and the metadata will be extracted and stored
	in a file called pkg-info in the same directory.

	All symlinks will be created to point to the correct location.

	The system root will be changed to the newly installed package's chroot directory.

	:raises ValueError: The package's control file is invalid.
	:raises FileNotFoundError: The package does not exist.
	:raises AssertionError: The package's path does not end with .deb.
	"""
	global root

	assert os.path.exists(path), "Supplied path does not exist!"
	assert path.lower()[-4:] == ".deb", "Path does not point to a .deb file!"
	# create pkg directory
	with TemporaryDirectory() as tmpdir:
		# extract pkg
		os.system(f"dpkg -x {path} {tmpdir}")
		# extract metadata
		info = get_deb_info(path)
		info = deb_to_pkg_info(info)
		# install package

		inst_dir = f"{root}/System/Packages/{info["Package"]["Name"]}***{info["Package"]["Version"]}"

		if os.path.exists(inst_dir):
			os.system(f"rm -R {inst_dir}")
		os.system(f"mkdir -p {inst_dir}")

		# create symlinks
		chroot = inst_dir + "/chroot"
		symlink(f"{chroot}/usr/bin", f"{chroot}/bin")
		symlink(f"{chroot}/usr/bin", f"{chroot}/usr/local/bin")
		symlink(f"{chroot}/usr/sbin", f"{chroot}/sbin")
		symlink(f"{chroot}/usr/lib", f"{chroot}/lib")
		symlink(f"{chroot}/usr/lib64", f"{chroot}/lib64")
		symlink(f"{chroot}/usr/etc", f"{chroot}/etc")
		symlink(f"{chroot}/usr/var", f"{chroot}/var")

		# os.system(f"cp -Ra {tmpdir}/. {inst_dir}/chroot")
		copy_tree(tmpdir, f"{inst_dir}/chroot")

		# install config
		os.system(f"touch {inst_dir}/pkg-info")
		with open(f"{inst_dir}/pkg-info", "w") as info_f:
			info_f.write(toml.dumps(info).replace("\\n", "\n"))

def get_pkg_list():
	"""
	Yields a dictionary of package metadata for each package in the system.

	Each dictionary returned has the following keys:
		- Name: The name of the package.
		- Version: A `packaging.version.Version` object representing the package version.
		- Path: The path to the package directory.
	"""
	packages = os.listdir(f"{root}/System/Packages")
	for pkg in packages:
		pkg_name = pkg.split("***")
		if len(pkg_name) != 2:
			print(f"Corrupt package in system! \"{pkg}\" Skipping for now.")
			continue
		pkg_ret = pkg_info_t(
			pkg_name[0],
			pkg_name[1],
			pkg
		)
		yield pkg_ret

def search_pkg_list(name: str, strict=False):
	"""
	Searches for packages in the system package list by name.

	This function iterates over the list of packages installed in the system
	and yields packages that match the given name. If `strict` is True,
	it yields packages with an exact name match. If `strict` is False,
	it yields packages that contain the given name as a substring.

	:param name: The name or substring to search for in package names.
	:param strict: A boolean indicating whether to perform a strict name match.
	:return: Yields dictionaries representing matched packages.
	"""
	global root

	for pkg in get_pkg_list():
		if strict:
			if pkg.name == name:
				yield pkg
		else:
			if name in pkg.name:
				yield name

def get_pkg(name: str):
	# We try to use the newest version availible to us.
	"""
	Returns the newest package matching the given name.

	This function iterates over the list of packages installed in the system
	and returns the newest package that matches the given name. If no packages
	match the given name, it returns None.

	:param name: The name of the package to search for.
	:return: A dictionary representing the newest package with a matching name.
	"""
	candidates = list(search_pkg_list(name))
	if not candidates: return None
	newest = None
	for candidate in candidates:
		if newest == None:
			newest = candidate
		else:
			if newest.version < candidate.version:
				newest = candidate
	return newest

def list_directory_tree(path: str) -> list:
	"""
	Returns a recursive list of all files and directories in the given path.

	:param path: The path to list the directory tree of.
	:return: A list of all files and directories (recursively) in the given path.
	"""
	files = []
	for root, dirs, filenames in os.walk(path):
		files.append(root)
		files.extend(os.path.join(root, f) for f in filenames)
	files.remove(path)
	return files

# Generate an occurence count of each element in a list
def occurence_count(l: list) -> dict:
	return {x: l.count(x) for x in l}

def generate_bwrap_args(deps: list) -> list:
	"""
	Generates a list of bubblewrap arguments for setting up the container environment.

	This function constructs bubblewrap arguments to set up the container with necessary
	overlays and bind mounts. The root of the system is mounted as an overlay for the source,
	and specific directories are bound to their respective locations.

	:param deps: A list of dependencies required for the container.
	:return: A list of bubblewrap arguments for container setup.
	"""
	global root
	args = []
	args += f"--overlay-src {root}"
	args += f"--tmp-overlay /"
	args += f"--bind {root}/System /System"
	args += f"--bind {root}/Users /Users"
	args += f"--bind {root}/Volumes /Volumes"

