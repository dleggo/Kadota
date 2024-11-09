#!/bin/python3

import os
from tempfile import TemporaryDirectory
import tomllib
import tomli_w
from packaging.version import Version
from collections import namedtuple
import argparse
from shutil import copytree

# Dependency = namedtuple('dep_info_t', ['name', 'comparison', 'version'])

root = ""

class Package:
	def __init__(self, name: str, version: Version, path: str):
		assert os.path.exists(path), "Package not found!"
		assert os.path.exists(path + "/pkg-info")
		self.name = name
		self.version = version
		self.path = path

	def get_info(path: str) -> dict:
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
		assert os.path.exists(path + "/pkg-info")
		with open(path + "/pkg-info", "r") as f:
			info = tomllib.load(f)
		return info

	def get_dependencies(path: str) -> list:
		"""
		Returns a list of dependencies for the package.

		This function reads the dependencies from the pkg-info file and returns
		a list of packages that the package depends on.

		:param path: The path to the package directory containing the pkg-info file.
		:return: A list of packages that the package depends on.
		:raises AssertionError: If the package directory or pkg-info file does not exist.
		"""
		info = Package.get_info(path)
		# TODO

	def __repr__(self):
		return f"Pkg({self.name}, {self.version}, {self.path})"

class Dependency:
	def __init__(self, name: str, comparison: str, version: Version):
		self.name = name
		self.comparison = comparison
		assert comparison in ["==", ">=", "<=", ">", "<", None], "Invalid comparison operator!"
		if type(version) == str:
			self.version = Version(version)
		else:
			self.version = version

	def satisfied_by(self, version: Version) -> bool:
		if self.comparison == "==":
			return self.version == version
		elif self.comparison == "=":
			return self.version == version
		elif self.comparison == ">=":
			return self.version <= version
		elif self.comparison == "<=":
			return self.version >= version
		elif self.comparison == ">":
			return self.version < version
		elif self.comparison == "<":
			return self.version > version
		else: # comparison == None
			return True

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

	:raises ValueError: If the control file is invalid
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
		copytree(
			tmpdir,
			f"{inst_dir}/chroot",
			symlinks=True,
			dirs_exist_ok=True
		)

		# install config
		os.system(f"touch {inst_dir}/pkg-info")
		with open(f"{inst_dir}/pkg-info", "w") as info_f:
			info_f.write(
				tomli_w.dumps(
					info,
					multiline_strings=True
				),
			)

def get_pkg_list():
	"""
	Yields a list of all packages in the system.
	"""
	packages = os.listdir(f"{root}/System/Packages")
	for pkg in packages:
		pkg_name = pkg.split("***")
		if len(pkg_name) != 2:
			print(f"Corrupt package in system! \"{pkg}\" Skipping for now.")
			continue
		pkg_ret = Package(
			pkg_name[0],
			Version(pkg_name[1]),
			f"{root}/System/Packages/{pkg}"
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
				yield pkg

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

def parse_dep(dep: str) -> Dependency:
	"""
	Parses a dependency string and returns a dep_info_t representing the parsed dependency.

	The dep_info_t structure has the following fields:
		- name: The name of the package.
		- comparison: The comparison operator used in the dependency string.
		- version: The version of the package.

	For example, if given the input "pkg1>=2.1.0", the output will be:
		dep_info_t("pkg1", ">=", "2.1.0")
	"""
	if "==" in dep:
		comparison = "=="
	elif ">=" in dep:
		comparison = ">="
	elif "<=" in dep:
		comparison = "<="
	else:
		dep_name = dep
		return Dependency(dep_name, None, None)

	dep_name = dep.split(comparison)[0]
	dep_version = dep.split(comparison)[1]
	return Dependency(dep_name, comparison, dep_version)

def get_deps_info(deps: list) -> list:
	"""
	Parses a list of dependencies and returns a
	list of dep_info_t representing the parsed dependencies.

	The dep_info_t structure has the following fields:
		- name: The name of the package.
		- comparison: The comparison operator used in the dependency string.
		- version: The version of the package.

	For example, if given the input ["pkg1>=2.1.0", "pkg2==3.2.1", "pkg3<=4.3.2", "pkg4"],
	the output will be:
	[
		dep_info_t("pkg1", ">=", "2.1.0"),
		dep_info_t("pkg2", "==", "3.2.1"),
		dep_info_t("pkg3", "<=", "4.3.2"),
		dep_info_t("pkg4", None, None)
	]
	"""
	deps_info = []
	for dep in deps:
		deps_info.append(parse_dep(dep))

	return deps_info

def deps_to_pkgs(deps_info: list) -> list:
	pkg_deps = []

	for dep in deps_info:
		pkgs = list(search_pkg_list(dep.name, strict=True))
		if not pkgs:
			raise ValueError(f"Could not find dependency \"{dep.name}\"")

		best = pkgs[0]
		for pkg in pkgs:
			if pkg.version > best.version and dep.satisfied_by(pkg.version):
				best = pkg
		pkg_deps.append(best)

	return pkg_deps

def occurence_count_item_t(l: list) -> dict:
	return {x: l.count(x) for x in l}

def generate_bwrap_args(deps: list) -> list:
	"""
	Generates a list of bubblewrap arguments for setting up the container environment.

	This function constructs bubblewrap arguments to set up the container with necessary
	overlays and bind mounts. The root of the system is mounted as an overlay for the source,
	and specific directories are bound to their respective locations.

	deps should be passed in a form of
	["pkg1==2.1.0", "pkg2>=3.2.1", "pkg3<=4.3.2"]

	:param deps: A list of dependencies required for the container.
	:return: A list of bubblewrap arguments for container setup.
	"""
	global root
	args = []
	args.append(f"--overlay-src {root}")
	args.append(f"--tmp-overlay /")
	args.append(f"--bind {root}/System /System")
	args.append(f"--bind {root}/Users /Users")
	args.append(f"--bind {root}/Volumes /Volumes")

	# generate list of packages that need to be included

	# Parse list of dependencies
	deps_info = get_deps_info(deps)

	# Get list of packages from list of dependencies
	deps = deps_to_pkgs(deps_info)

	# item_t = namedtuple('item_t', ['bwrap_loc', 'fullpath', 'pkg', "occurences"])
	class item_t:
		def __init__(self, bwrap_loc, fullpath, pkg, occurences):
			self.bwrap_loc = bwrap_loc
			self.fullpath = fullpath
			self.pkg = pkg
			self.occurences = occurences
		def __repr__(self):
			return f"item_t({self.bwrap_loc}, {self.fullpath}, {self.pkg}, {self.occurences})"

	# generate trees of all of them, and merge them together
	directories = []
	files = []
	for dep in deps:
		# for each dependency...
		dep_root = os.path.join(dep.path, "chroot")
		dep_contents = list_directory_tree(dep_root)
		for dep_item in dep_contents:
			if os.path.isdir(dep_item):
				directories.append(item_t(
					dep_item[len(dep_root):], # removes down the common prefix
					dep_item,
					dep,
					None
				))
			elif os.path.isfile(dep_item):
				files.append(item_t(
					dep_item[len(dep_root):], # removes down the common prefix
					dep_item,
					dep,
					None
				))

	# So now we have a list of all the files and directories that need to be included
	# This list is massive but we must not panic...

	# generate a dictionary of all of them with their occurence count
	# files, and directories are all of type item_t
	# so we need to convert them to their bwrap location

	directories_bwrap_locations = [x.bwrap_loc for x in directories]
	files_bwrap_locations = [x.bwrap_loc for x in files]

	dirs_occ = occurence_count(directories_bwrap_locations)
	files_occ = occurence_count(files_bwrap_locations)

	for dir,occ in zip(directories, dirs_occ):
		dir.occurences = occ

	for file,occ in zip(files, files_occ):
		file.occurences = occ

	# We need to follow the rules defined in Pkgs.md

	# for each directory...
	# if occurence count = 1, symlink
	# if occurence count > 1, create directory

	for dir in directories:
		print(dir)

	# for each file...
	# if occurence count = 1, symlink
	# if occurence count > 1, only the file closest to the main package will be symlinked

	for file in files:
		print(file)



	# generate mkdirs
	# generate symlinks

	return args