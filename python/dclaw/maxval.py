import argparse
import glob
import os

import fiona
import numpy as np
import rasterio
import rasterio.transform
from dclaw.fortconvert import convertfortdir
from dclaw.get_data import get_dig_data, get_region_data
from rasterio import features
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


def main():
    parser = argparse.ArgumentParser(
        prog="gridded_maxval",
        description=(
            "Calculate maximum value over a amrclaw region or in the box bounded "
            "by north, west, east, and south. All timesteps are used. First fort "
            "format output is converted to .tif. Then a maximum is calculated. "
            "Cptionally, a shapefile of the extent is generated."
        ),
        usage="%(prog)s [options]",
    )

    parser.add_argument(
        "-wd", "--wdir", nargs="?", help="Working directory", default=".", type=str
    )

    parser.add_argument(
        "-od",
        "--odir",
        nargs="?",
        help="Directory within wd containing fort files",
        default="_output",
        type=str,
    )

    parser.add_argument(
        "-gd",
        "--gdir",
        nargs="?",
        help="Directory within --wdir to place gridded files",
        default="_gridded_output",
        type=str,
    )

    parser.add_argument(
        "-of",
        "--outfile",
        nargs="?",
        help="Output maximum value file name. Placed in -wdir",
        default="maxval.tif",
        type=str,
    )

    parser.add_argument(
        "-cd",
        "--check_done",
        action="store_true",
        default=True,
        help="Check if file processing has already occured and only reprocess new or updated files.",
    )

    parser.add_argument(
        "-nc",
        "--num_cores",
        nargs="?",
        help="Number of cores for fortconvert",
        default=8,
        type=int,
    )

    parser.add_argument(
        "-epsg",
        "--epsg",
        nargs="?",
        help="EPSG code to use for output .tif and .shp files",
        default=None,
    )

    parser.add_argument(
        "-w",
        "--west",
        nargs="?",
        help="West extent of bounding box.",
        default=None,
        type=int,
    )
    parser.add_argument(
        "-e",
        "--east",
        nargs="?",
        help="East extent of bounding box.",
        default=None,
        type=int,
    )
    parser.add_argument(
        "-n",
        "--north",
        nargs="?",
        help="North extent of bounding box.",
        default=None,
        type=int,
    )
    parser.add_argument(
        "-s",
        "--south",
        nargs="?",
        help="South extent of bounding box.",
        default=None,
        type=int,
    )
    parser.add_argument(
        "-r",
        "--region",
        nargs="?",
        help="Amrclaw region number to use for extent. Will overwrite east/south/north/west, if provided.",
        default=None,
        type=int,
    )

    parser.add_argument(
        "-wf",
        "--write_froude",
        help="Write a froude number maximum in the tif.",
        default=False,
        action="store_false",
    )

    parser.add_argument(
        "-shp",
        "--extent_shp",
        help="Write a shapefile with the extent of values greater than a specified threashold.",
        action="store_false",
    )
    parser.add_argument(
        "-sval",
        "--extent_shp_val",
        nargs="?",
        help="Quantity to use for defining the extent of values greater.",
        default="height",
        choices=["height", "momentum", "velocity"],
        type=str,
    )
    parser.add_argument(
        "-sth",
        "--extent_shp_val_thresh",
        nargs="?",
        default=0.0,
        type=float,
        help="Threshold. Default value of 0, along with 'height' yeilds inundated area",
    )
    parser.add_argument(
        "-sof",
        "--extent_shp_val_out_file",
        nargs="?",
        default="extent.shp",
        type=str,
        help="Name of output shapefile.",
    )

    args = parser.parse_args()

    # do some checking with the region.

    if args.region is not None:
        region_data = get_region_data(args.wdir, args.odir)
        west = region_data[args.region]["x1"]
        east = region_data[args.region]["x2"]
        south = region_data[args.region]["y1"]
        north = region_data[args.region]["y2"]
    else:
        west = args.west
        east = args.east
        south = args.south
        north = args.north
    # make output dir
    if not os.path.exists(os.path.join(args.wdir, args.gdir)):
        os.mkdir(os.path.join(args.wdir, args.gdir))

    # check which files to convert. Could do a temporal filter here..
    files = glob.glob(os.path.join(args.wdir, *[args.odir, "fort.q*"]))
    ntifs = glob.glob(os.path.join(args.wdir, *[args.gdir, "fort_q*.tif"]))

    nfiles = []

    # print(args.check_done)
    for file in files:
        numstr = os.path.basename(file)[6:]
        tifname = os.path.join(
            ".",
            *[os.path.join(args.wdir, args.gdir), "fort_q{}.tif".format(numstr)]
        )
        if os.path.exists(tifname) and args.check_done:
            mtime_fort = os.path.getmtime(file)
            mtime_tif = os.path.getmtime(tifname)
            if mtime_tif > mtime_fort:
                process = False
            else:
                process = True
        else:
            process = True
        if process:
            nfiles.append(int(numstr))
    nfiles = np.sort(nfiles)

    if len(nfiles) == 0:
        print("check_done = True and no new files to process. No files reprocessed.")
    else:
        print("Processing {} files: {}".format(len(nfiles), nfiles))

        convertfortdir(
            "fortrefined",
            nplots=nfiles,
            outputname="fort_q",
            components="all",
            outdir=os.path.join(args.wdir, args.gdir),
            fortdir=os.path.join(args.wdir, args.odir),
            parallel=True,
            num_cores=args.num_cores,
            topotype="gtif",
            write_level=True,
            epsg=args.epsg,
            west=west,
            east=east,
            south=south,
            north=north,
        )

    dig_data = get_dig_data(args.wdir, args.odir)
    rho_f = dig_data["rho_f"]
    rho_s = dig_data["rho_s"]

    dclaw2maxval_withlev(
        wdir=args.wdir,
        gdir=args.gdir,
        out_file="maxval.tif",
        write_froude=args.write_froude,
        epsg=args.epsg,
        rho_f=rho_f,
        rho_s=rho_s,
        extent_shp=args.extent_shp,
        extent_shp_val=args.extent_shp_val,
        extent_shp_val_thresh=args.extent_shp_val_thresh,
        extent_shp_val_out_file=args.extent_shp_val_out_file,
    )


def dclaw2maxval_withlev(
    wdir=".",
    gdir="_gridded_output",
    nplots=None,
    out_file=None,
    rho_f=1000,
    rho_s=2700,
    epsg=None,
    write_froude=False,
    extent_shp=True,
    extent_shp_val="height",
    extent_shp_val_thresh=0.0,
    extent_shp_val_out_file=None,
):

    out_file = out_file or os.path.join(wdir, "maxval.tif")
    extent_shp_val_out_file = extent_shp_val_out_file or os.path.join(
        wdir, "extent.shp"
    )

    # loop through fortq files and add:

    if epsg is not None:
        crs = rasterio.crs.CRS.from_epsg(epsg)
    else:
        crs = None

    files = np.sort(glob.glob(os.path.join(wdir, gdir, "*.tif")))
    if len(files) == 0:
        raise ValueError("no files")

    # Read them all in.
    with rasterio.open(files[0], "r") as src:
        dims = (src.meta["height"], src.meta["width"])

    hmin_fill = 99999.0
    h_max = np.zeros(dims, dtype="float32")
    h_min = np.ones(dims, dtype="float32")
    h_min[:] = hmin_fill
    m_max = np.zeros(dims, dtype="float32")
    vel_max = np.zeros(dims, dtype="float32")
    mom_max = np.zeros(dims, dtype="float32")
    eta_max = np.zeros(dims, dtype="float32")
    lev_max = np.zeros(dims, dtype="float32")
    froude_max = np.zeros(dims, dtype="float32")

    h_max_lev = np.zeros(dims, dtype=int)
    h_min_lev = np.zeros(dims, dtype=int)
    m_max_lev = np.zeros(dims, dtype=int)
    vel_max_lev = np.zeros(dims, dtype=int)
    mom_max_lev = np.zeros(dims, dtype=int)
    eta_max_lev = np.zeros(dims, dtype=int)
    froude_max_lev = np.zeros(dims, dtype=int)

    arrival_time = -1 * np.ones(dims, dtype="float32")
    eta_max_time = -1 * np.ones(dims, dtype="float32")
    vel_max_time = -1 * np.ones(dims, dtype="float32")

    for file in files:
        fortt = file[:-4].replace("fort_q", "fort.t")
        # print(file)
        frameno = int(file[-8:-4])

        calc = True
        if nplots is not None:
            if frameno not in nplots:
                calc = False
        if calc:
            # print(file[-8:-4], frameno)
            with open(fortt, "r") as f:
                lines = f.readlines()
            time = float(lines[0].split()[0])
            with rasterio.open(file, "r") as src:
                profile = src.profile
                transform = src.transform

                dx = transform[0]

                h = src.read(1)
                hu = src.read(2)
                hv = src.read(3)
                hm = src.read(4)
                eta = src.read(8)
                level = src.read(9)

                with np.errstate(divide="ignore", invalid="ignore"):
                    m = hm / h
                    m[np.isnan(m)] = 0
                    vel = ((hu / h) ** 2 + (hv / h) ** 2) ** 0.5
                    vel[np.isnan(vel)] = 0

                    froude = vel / np.sqrt(9.81 * h)

                density = (1.0 - m) * rho_f + (m * rho_s)
                mom = (h * dx * dx) * density * vel

                maxlevel = level.max()

                # keep track of max level anywhere.
                lev_max[level > lev_max] = level[level > lev_max]

                # determine whether to overwrite.
                overwrite_eta = ((level >= eta_max_lev) & (eta > eta_max)) | (
                    level > eta_max_lev
                )
                overwrite_h_max = ((level >= h_max_lev) & (h > h_max)) | (
                    level > h_max_lev
                )
                overwrite_h_min = ((level >= h_min_lev) & (h < h_min)) | (
                    level > h_min_lev
                )

                overwrite_m = ((level >= m_max_lev) & (m > m_max)) | (level > m_max_lev)
                overwrite_vel = ((level >= vel_max_lev) & (vel > vel_max)) | (
                    level > vel_max_lev
                )
                overwrite_mom = ((level >= mom_max_lev) & (mom > mom_max)) | (
                    level > mom_max_lev
                )

                overwrite_froude = (
                    (level >= froude_max_lev) & (froude > froude_max)
                ) | (level > froude_max_lev)
                # update max level seen.
                eta_max_lev[overwrite_eta] = level[overwrite_eta]
                h_max_lev[overwrite_h_max] = level[overwrite_h_max]
                h_min_lev[overwrite_h_min] = level[overwrite_h_min]
                m_max_lev[overwrite_m] = level[overwrite_m]
                vel_max_lev[overwrite_vel] = level[overwrite_vel]
                mom_max_lev[overwrite_mom] = level[overwrite_mom]
                froude_max_lev[overwrite_froude] = level[overwrite_froude]

                # update arrival time, also set other times to this, to indicate the wave has arrived there and thus its valid to
                # set a max.
                # set arrival time to the first timestep that has eta>0.01 and highest level.
                overwrite_arrival = (
                    (eta > 0.01) & (arrival_time < 0) & (level == maxlevel)
                )

                arrival_time[overwrite_arrival] = time
                eta_max_time[overwrite_arrival] = time
                vel_max_time[overwrite_arrival] = time

                # update max values.
                h_max[overwrite_h_max] = h[overwrite_h_max]
                h_min[overwrite_h_min] = h[overwrite_h_min]
                m_max[overwrite_m] = m[overwrite_m]
                vel_max[overwrite_vel] = vel[overwrite_vel]
                mom_max[overwrite_mom] = mom[overwrite_mom]
                eta_max[overwrite_eta] = eta[overwrite_eta]
                froude_max[overwrite_froude] = froude[overwrite_froude]

                # we want the first peak.
                not_super_late = ((time - eta_max_time) < 1 * 60) & (arrival_time >= 0)

                # use 10 minutes
                # presuming time has been set.
                # presuming the arrival time has passed.

                overwrite_eta_time = overwrite_eta & not_super_late
                overwrite_vel_time = overwrite_vel & not_super_late

                eta_max_time[overwrite_eta_time] = time
                vel_max_time[overwrite_vel_time] = time

    never_inundated = h_max < 0.00001
    h_max[never_inundated] = np.nan
    h_min[h_min == 0] = np.nan
    m_max[never_inundated] = np.nan
    vel_max[never_inundated] = np.nan
    mom_max[never_inundated] = np.nan
    eta_max_time[never_inundated] = np.nan
    vel_max_time[never_inundated] = np.nan
    arrival_time[never_inundated] = np.nan
    froude_max[never_inundated] = np.nan
    # where less than zero, wave never reached.
    eta_max_time[eta_max_time < 0] = np.nan
    vel_max_time[vel_max_time < 0] = np.nan
    arrival_time[arrival_time < 0] = np.nan

    # then read in grided output into t, h, m, vel, mom, etc.
    # clip to required extent.

    # calculate output bands and write out as .tif
    # this is also where we figure out time of h max and time of vel max.

    out_profile = profile
    out_profile["height"], out_profile["width"] = m_max.shape
    out_profile["dtype"] = "float32"
    out_profile["count"] = 10
    out_profile["transform"] = transform

    if write_froude:
        out_profile["count"] = 11
    with rasterio.open(out_file, "w", **out_profile) as dst:
        dst.write(h_max, 1)
        dst.write(vel_max, 2)
        dst.write(mom_max, 3)
        dst.write(m_max, 4)
        dst.write(eta_max_time, 5)
        dst.write(vel_max_time, 6)
        dst.write(eta_max, 7)
        dst.write(lev_max, 8)
        dst.write(arrival_time, 9)
        dst.write(h_min, 10)
        if write_froude:
            dst.write(froude_max, 11)

    if extent_shp:
        if extent_shp_val == "height":
            extent = h_max > extent_shp_val_thresh
        if extent_shp_val == "momentum":
            extent = mom_max > extent_shp_val_thresh
        if extent_shp_val == "velocity":
            extent = vel_max > extent_shp_val_thresh
        transform = out_profile["transform"]
        geoms = []
        for i, (s, v) in enumerate(
            features.shapes(extent.astype(np.int16), mask=extent, transform=transform)
        ):
            geoms.append(shape(s))
        out_shp = unary_union(geoms).buffer(0)
        assert out_shp.is_valid == True
        with fiona.open(
            extent_shp_val_out_file,
            "w",
            driver="Shapefile",
            crs=crs,
            schema={"properties": [], "geometry": "Polygon"},
        ) as dst:
            dst.writerecords([{"properties": {}, "geometry": mapping(out_shp)}])
