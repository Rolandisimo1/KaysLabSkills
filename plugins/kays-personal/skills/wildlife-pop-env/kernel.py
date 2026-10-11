VERSION = "2"
RLIB_ARTIFACT = "wildlife_pop_rlib.tar.gz"
RLIB_REL = "./.r-libs/wildlife-pop"

def wildlife_r_setup(host_obj):
    """Restore the wildlife R library into the workspace if absent.

    Call from a `python` cell (env `wildlife-pop`) BEFORE the first `r` cell of
    a session; pass the kernel's `host` object. Returns a status dict.
    Idempotent: if the library is already present it does nothing.
    """
    import os, tarfile
    target = os.path.join(".r-libs", "wildlife-pop")
    if os.path.isdir(target) and len(os.listdir(target)) > 50:
        return {"status": "present", "path": os.path.abspath(target),
                "n_packages": len(os.listdir(target))}
    hits = host_obj.artifacts(filename=RLIB_ARTIFACT, exact=True)["artifacts"]
    if not hits:
        return {"status": "missing_artifact", "artifact": RLIB_ARTIFACT}
    path = host_obj.artifact_path(hits[0]["latest_version_id"])
    os.makedirs(".r-libs", exist_ok=True)
    with tarfile.open(path) as t:
        t.extractall(".r-libs", filter="data")
    return {"status": "restored", "path": os.path.abspath(target),
            "n_packages": len(os.listdir(target))}

def wildlife_r_libpaths_snippet():
    """The .libPaths() line that must open every R session in this env."""
    return ('.libPaths(c(normalizePath("./.r-libs/wildlife-pop"), '
            'file.path(Sys.getenv("CONDA_PREFIX"), "lib/R/library")))')
