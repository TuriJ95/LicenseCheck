"""Get information for installed and online packages.
"""
from __future__ import annotations

from importlib import metadata, resources
from pathlib import Path
from typing import Any, cast
import configparser

import requests
import tomli

from licensecheck.types import PackageInfo

UNKNOWN = "UNKNOWN"


def getPackagesFromLocal(requirements: list[str]) -> list[PackageInfo]:
	"""Get a list of package info from local files including version, author
	and	the license.

	Args:
		requirements (list[str]): [description]

	Returns:
		list[PackageInfo]: [description]
	"""
	pkgInfo = []
	for requirement in requirements:
		try:
			# Get pkg metadata: license, homepage + author
			pkgMetadata = metadata.metadata(requirement)
			lice = licenseFromClassifierlist(
				[val for key, val in pkgMetadata.items() if key == "Classifier"]
			)
			if lice == UNKNOWN:
				lice = pkgMetadata.get("License", UNKNOWN)
			homePage = pkgMetadata.get("Home-page", UNKNOWN)
			author = pkgMetadata.get("Author", UNKNOWN)
			name = pkgMetadata.get("Name", UNKNOWN)
			version = pkgMetadata.get("Version", UNKNOWN)
			size = 0
			try:
				packagePath = resources.files(requirement)
				size = getModuleSize(cast(Path, packagePath), name)
			except TypeError:
				pass
			# append to pkgInfo
			pkgInfo.append(
				{
					"name": name,
					"version": version,
					"namever": f"{name}-{version}",
					"home_page": homePage,
					"author": author,
					"size": size,
					"license": lice,
				}
			)
		except (metadata.PackageNotFoundError, ModuleNotFoundError):
			pass
	return pkgInfo


def packageInfoFromPypi(requirements: list[str]) -> list[PackageInfo]:
	"""Get a list of package info from pypi.org including version, author
	and	the license.

	Args:
		requirements (list[str]): [description]

	Returns:
		list[PackageInfo]: [description]
	"""
	pkgInfo = []
	for pkg in requirements:
		request = requests.get(f"https://pypi.org/pypi/{pkg}/json", timeout=60)
		response = request.json()
		info = response["info"]
		licenseClassifier = licenseFromClassifierlist(info["classifiers"])
		pkgInfo.append(
			{
				"name": pkg,
				"version": info["version"],
				"namever": f"{pkg} {info['version']}",
				"home_page": info["home_page"],
				"author": info["author"],
				"size": int(response["urls"][-1]["size"]),
				"license": licenseClassifier if licenseClassifier != UNKNOWN else info["license"],
			}
		)
	return pkgInfo


def licenseFromClassifierlist(classifiers: list[str]) -> str:
	"""Get license string from a list of project classifiers.

	Args:
		classifiers (list[str]): list of classifiers

	Returns:
		str: the license name
	"""
	licenses = []
	for val in classifiers:
		if val.startswith("License"):
			lice = val.split(" :: ")[-1]
			if lice != "OSI Approved":
				licenses.append(lice)
	return ", ".join(licenses) if len(licenses) > 0 else UNKNOWN


def getPackages(reqs: list[str]) -> list[PackageInfo]:
	"""Get dependency info.

	Args:
		reqs (list[str]): list of dependency names to gather info on

	Returns:
		list[PackageInfo]: list of dependencies
	"""
	localReqs = getPackagesFromLocal(reqs)
	for localReq in localReqs:
		reqs.remove(localReq["name"].lower())
	onlineReqs = packageInfoFromPypi(reqs)
	return localReqs + onlineReqs

def getClassifiersLicense() -> dict[str, Any]:
	"""Get the package classifiers and license from "setup.cfg", "pyproject.toml" or user input

	Returns:
		dict[str, Any]: {"classifiers": list[str], "license": str}
	"""
	if Path("setup.cfg").exists():
		config = configparser.ConfigParser()
		_ = config.read("setup.cfg")
		if "license" in config["metadata"]:
			return config["metadata"].__dict__
	if Path("pyproject.toml").exists():
		pyproject = tomli.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
		tool = pyproject["tool"]
		if "poetry" in tool:
			return tool["poetry"]
		if "flit" in tool:
			return tool["flit"]["metadata"]
		if pyproject.get("project") is not None:
			return pyproject["project"]

	return {"classifiers": [], "license": ""}



def getMyPackageLicense() -> str:
	"""Get the package license from "setup.cfg", "pyproject.toml" or user input

	Returns:
		str: license name
	"""
	metaData = getClassifiersLicense()
	licenseClassifier = licenseFromClassifierlist(metaData.get("classifiers", []))
	if licenseClassifier != UNKNOWN:
		return licenseClassifier
	if "license" in metaData:
		if isinstance(metaData["license"], dict) and metaData["license"].get("text") is not None:
			return str(metaData["license"].get("text"))
		else:
			return str(metaData["license"])
	return input("Enter the project license")



def getModuleSize(path: Path, name: str) -> int:
	"""Get the size of a given module as an int.

	Args:
		path (Path): path to package
		name (str): name of package

	Returns:
		int: size in bytes
	"""
	size = sum(
		f.stat().st_size for f in path.glob("**/*") if f.is_file() and "__pycache__" not in str(f)
	)
	if size > 0:
		return size
	request = requests.get(f"https://pypi.org/pypi/{name}/json", timeout=60)
	response = request.json()
	return int(response["urls"][-1]["size"])
