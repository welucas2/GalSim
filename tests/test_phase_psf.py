# Copyright (c) 2012-2023 by the GalSim developers team on GitHub
# https://github.com/GalSim-developers
#
# This file is part of GalSim: The modular galaxy image simulation toolkit.
# https://github.com/GalSim-developers/GalSim
#
# GalSim is free software: redistribution and use in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions, and the disclaimer given in the accompanying LICENSE
#    file.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions, and the disclaimer given in the documentation
#    and/or other materials provided with the distribution.
#

import os
import numpy as np
import pickle

import galsim
from galsim_test_helpers import *


imgdir = os.path.join(".", "Optics_comparison_images") # Directory containing the reference images.
pp_file = 'sample_pupil_rolled.fits'

theta0 = (0*galsim.arcmin, 0*galsim.arcmin)

# The timing tests can be unreliable in environments with other processes running at the
# same time.  So we disable them by default.  However, on a clean system, they should all pass.
test_timing = False


@timer
def test_aperture():
    """Test various ways to construct Apertures."""
    # Simple tests for constructing and pickling Apertures.
    aper1 = galsim.Aperture(diam=1.7)
    im = galsim.fits.read(os.path.join(imgdir, pp_file))
    aper2 = galsim.Aperture(diam=1.7, pupil_plane_im=im)
    aper3 = galsim.Aperture(diam=1.7, nstruts=4, gsparams=galsim.GSParams(maximum_fft_size=4096))
    check_pickle(aper1)
    check_pickle(aper2)
    check_pickle(aper3)
    # Automatically created Aperture should match one created via OpticalScreen
    aper1 = galsim.Aperture(diam=1.7)
    aper2 = galsim.Aperture(diam=1.7, lam=500, screen_list=[galsim.OpticalScreen(diam=1.7)])
    err_str = ("Aperture created implicitly using Airy does not match Aperture created using "
               "OpticalScreen.")
    assert aper1 == aper2, err_str

    assert_raises(ValueError, galsim.Aperture, 1.7, obscuration=-0.3)
    assert_raises(ValueError, galsim.Aperture, 1.7, obscuration=1.1)
    assert_raises(ValueError, galsim.Aperture, -1.7)
    assert_raises(ValueError, galsim.Aperture, 0)

    assert_raises(ValueError, galsim.Aperture, 1.7, pupil_plane_im=im, circular_pupil=False)
    assert_raises(ValueError, galsim.Aperture, 1.7, pupil_plane_im=im, nstruts=2)
    assert_raises(ValueError, galsim.Aperture, 1.7, pupil_plane_im=im, strut_thick=0.01)
    assert_raises(ValueError, galsim.Aperture, 1.7, pupil_plane_im=im, strut_angle=5*galsim.degrees)
    assert_raises(ValueError, galsim.Aperture, 1.7, pupil_plane_im=im, strut_angle=5*galsim.degrees)
    assert_raises(ValueError, galsim.Aperture, 1.7, screen_list=[galsim.OpticalScreen(diam=1)])
    assert_raises(TypeError, galsim.Aperture, 1.7, nstruts=4, strut_angle=5)
    assert_raises(TypeError, galsim.Aperture, 1.7, pupil_plane_im=im, pupil_angle=5)

    # rho is a convenience property that can be useful when debugging, but isn't used in the
    # main code base.
    np.testing.assert_almost_equal(aper1.rho, aper1.u * 2./1.7 + 1j * aper1.v * 2./1.7)

    # Some other functions that aren't used by anything anymore, but were useful in development.
    for lam in [300, 550, 1200]:
        stepk = aper1._getStepK(lam=lam)
        maxk = aper1._getMaxK(lam=lam)
        scale = aper1._sky_scale(lam=lam)
        size = aper1._sky_size(lam=lam)
        np.testing.assert_almost_equal(stepk, 2.*np.pi/size)
        np.testing.assert_almost_equal(maxk, np.pi/scale)

    # If the constructed pupil plane would be too large, raise an error
    with assert_raises(galsim.GalSimFFTSizeError):
        ap = galsim.Aperture(1.7, pupil_plane_scale=1.e-4)
        ap._illuminated  # Only triggers once we force it to build the illuminated array

    # Similar if the given image is too large.
    # Here, we change gsparams.maximum_fft_size, rather than build a really large image to load.
    with assert_raises(galsim.GalSimFFTSizeError):
        ap = galsim.Aperture(1.7, pupil_plane_im=im, gsparams=galsim.GSParams(maximum_fft_size=64))
        ap._illuminated

    # Other choices just give warnings about pupil scale or size being inappropriate
    with assert_warns(galsim.GalSimWarning):
        ap = galsim.Aperture(diam=1.7, pupil_plane_size=3, pupil_plane_scale=0.03)
        ap._illuminated

    im.wcs = None  # Otherwise get an error.
    with assert_warns(galsim.GalSimWarning):
        ap = galsim.Aperture(diam=1.7, pupil_plane_im=im, pupil_plane_scale=0.03)
        ap._illuminated


@timer
def test_atm_screen_size():
    """Test for consistent AtmosphericScreen size and scale."""
    screen_size = 10.0
    screen_scale = 0.1
    atm = galsim.AtmosphericScreen(screen_size=screen_size, screen_scale=screen_scale)
    # AtmosphericScreen will preserve screen_scale, but will adjust screen_size as necessary to get
    # a good FFT size.
    assert atm.screen_scale == screen_scale
    assert screen_size < atm.screen_size < 1.5*screen_size
    np.testing.assert_equal(atm.screen_size, atm.npix * atm.screen_scale,
                            "Inconsistent atmospheric screen size and scale.")


@timer
def test_structure_function(run_slow):
    """Test that AtmosphericScreen generates the right structure function.
    """
    if run_slow:
        L0s = [10.0, 25.0, 100.0]
        screen_size = 300.0
    else:
        L0s = [10.0]
        screen_size = 100.0

    rng = galsim.BaseDeviate(4815162342)
    lam = 500.0
    r0_500 = 0.2
    screen_scale = 0.05

    for L0 in L0s:
        screen = galsim.AtmosphericScreen(screen_size=screen_size, screen_scale=screen_scale,
                                          r0_500=r0_500, L0=L0, rng=rng)
        screen.instantiate()
        vk = galsim.VonKarman(lam=lam, r0=r0_500*(lam/500.0)**1.2, L0=L0)
        phase = screen._tab2d.getVals()[:-1, :-1] * 2 * np.pi / 500.0  # nm -> radians

        var = np.var(phase)
        # Conan 2008 eq 16
        # 0.0863 ~= Gamma(11/6) Gamma(5/6) / (2 pi^(8/3)) (24/5 Gamma(6/5))^(5/6)
        expected_var = 0.0863 * (r0_500/L0)**(-5/3.)
        np.testing.assert_allclose(
            var, expected_var, rtol=0.025,
            err_msg="Simulated variance disagrees with expected variance.")

        im = galsim.Image(phase, scale=screen_scale)
        D_sim = galsim.utilities.structure_function(im)

        print("r     D_VK     D_sim")
        for r in [0.1, 1.0, 10.0]:
            analytic_SF = vk._structure_function(r)
            simulated_SF = D_sim(r)
            print(r, analytic_SF, simulated_SF)
            np.testing.assert_allclose(
                    analytic_SF, simulated_SF, rtol=0.05,
                    err_msg="Simulated structure function not close to prediction.")


@timer
def test_phase_screen_list():
    """Test list-like behaviors of PhaseScreenList."""
    rng = galsim.BaseDeviate(1234)
    rng2 = galsim.BaseDeviate(123)

    aper = galsim.Aperture(diam=1.0)

    ar1 = galsim.AtmosphericScreen(10, 1, alpha=0.997, L0=None, time_step=0.01, rng=rng)
    assert ar1._time == 0.0, "AtmosphericScreen initialized with non-zero time."
    check_pickle(ar1)
    check_pickle(ar1, func=lambda x: x.wavefront(aper.u, aper.v, 0.0).sum())
    check_pickle(ar1, func=lambda x: np.sum(x.wavefront_gradient(aper.u, aper.v, 0.0)))
    t = np.empty_like(aper.u)
    ud = galsim.UniformDeviate(rng.duplicate())
    ud.generate(t.ravel())
    t *= 0.1  # Only do a few boiling steps
    check_pickle(ar1, func=lambda x: x.wavefront(aper.u, aper.v, t).sum())
    check_pickle(ar1, func=lambda x: np.sum(x.wavefront_gradient(aper.u, aper.v, t)))

    # Try seeking backwards
    assert ar1._time > 0.0
    ar1._seek(0.0)
    # But not before t=0.0
    with assert_raises(ValueError):
        ar1._seek(-1.0)

    # Check that L0=np.inf and L0=None yield the same thing here too.
    ar2 = galsim.AtmosphericScreen(10, 1, alpha=0.997, L0=np.inf, time_step=0.01, rng=rng)
    # Before ar2 is instantiated, it's unequal to ar1, even though they were initialized with the
    # same arguments (the hashes are the same though).  After both have been instantiated with the
    # same range of k (ar1 through use of .wavefront() and ar2 explicitly), then they are equal (
    # and the hashes are still the same).
    assert hash(ar1) == hash(ar2)
    assert ar1 != ar2
    ar2.instantiate()
    assert ar1 == ar2
    assert hash(ar1) == hash(ar2)
    # Create a couple new screens with different types/parameters
    ar2 = galsim.AtmosphericScreen(10, 1, alpha=0.995, time_step=0.015, rng=rng2)
    ar2.instantiate()
    assert ar1 != ar2
    ar3 = galsim.OpticalScreen(diam=1.0, aberrations=[0, 0, 0, 0, 0, 0, 0, 0, 0.1],
                               obscuration=0.3, annular_zernike=True)
    check_pickle(ar3)
    check_pickle(ar3, func=lambda x:x.wavefront(aper.u, aper.v).sum())
    check_pickle(ar3, func=lambda x:np.sum(x.wavefront_gradient(aper.u, aper.v)))
    atm = galsim.Atmosphere(screen_size=30.0,
                            altitude=[0.0, 1.0],
                            speed=[1.0, 2.0],
                            direction=[0.0*galsim.degrees, 120*galsim.degrees],
                            r0_500=0.15,
                            rng=rng)
    atm.append(ar3)
    check_pickle(atm)
    check_pickle(atm, func=lambda x:x.wavefront(aper.u, aper.v, 0.0, theta0).sum())
    check_pickle(atm, func=lambda x:np.sum(x.wavefront_gradient(aper.u, aper.v, 0.0)))

    # testing append, extend, __getitem__, __setitem__, __delitem__, __eq__, __ne__
    atm2 = atm[:-1]  # Refers to first n-1 screens
    assert atm != atm2
    # Append a different screen to the end of atm2
    atm2.append(ar2)
    assert atm != atm2
    # Swap the last screen in atm2 for the one that should match atm.
    del atm2[-1]
    atm2.append(atm[-1])
    assert atm == atm2

    with assert_raises(TypeError):
        atm['invalid']
    with assert_raises(IndexError):
        atm[3]

    # Test building from empty PhaseScreenList
    atm3 = galsim.PhaseScreenList()
    atm3.extend(atm2)
    assert atm == atm3

    # Test constructing from existing PhaseScreenList
    atm4 = galsim.PhaseScreenList(atm3)
    del atm4[-1]
    assert atm != atm4
    atm4.append(atm[-1])
    assert atm == atm4

    # Test swap
    atm4[0], atm4[1] = atm4[1], atm4[0]
    assert atm != atm4
    atm4[0], atm4[1] = atm4[1], atm4[0]
    assert atm == atm4

    wf = atm.wavefront(aper.u, aper.v, None, theta0)
    wf2 = atm2.wavefront(aper.u, aper.v, None, theta0)
    wf3 = atm3.wavefront(aper.u, aper.v, None, theta0)
    wf4 = atm4.wavefront(aper.u, aper.v, None, theta0)

    np.testing.assert_array_equal(wf, wf2, "PhaseScreenLists are inconsistent")
    np.testing.assert_array_equal(wf, wf3, "PhaseScreenLists are inconsistent")
    np.testing.assert_array_equal(wf, wf4, "PhaseScreenLists are inconsistent")

    # Check copy
    import copy
    # Shallow copy copies by reference.
    atm5 = copy.copy(atm)
    assert atm[0] == atm5[0]
    assert atm[0] is atm5[0]
    atm._seek(1.0)
    assert atm[0]._time == 1.0, "Wrong time for AtmosphericScreen"
    assert atm[0] == atm5[0]
    assert atm[0] is atm5[0]
    # Deepcopy actually makes an indepedent object in memory.
    atm5 = copy.deepcopy(atm)
    assert atm[0] == atm5[0]
    assert atm[0] is not atm5[0]
    atm._seek(2.0)
    assert atm[0]._time == 2.0, "Wrong time for AtmosphericScreen"
    # But we still get equality, since this doesn't depend on mutable internal state:
    assert atm[0] == atm5[0]

    # Constructor should accept both list and indiv layers as arguments.
    atm6 = galsim.PhaseScreenList(atm[0])
    atm7 = galsim.PhaseScreenList([atm[0]])
    assert atm6 == atm7
    check_pickle(atm6, func=lambda x:x.wavefront(aper.u, aper.v, None, theta0).sum())
    check_pickle(atm6, func=lambda x:np.sum(x.wavefront_gradient(aper.u, aper.v, 0.0)))

    atm6 = galsim.PhaseScreenList(atm[0], atm[1])
    atm7 = galsim.PhaseScreenList([atm[0], atm[1]])
    atm8 = galsim.PhaseScreenList(atm[0:2])  # Slice returns PhaseScreenList, so this works too.
    assert atm6 == atm7
    assert atm6 == atm8

    # Check some actual derived PSFs too, not just phase screens.  Use a small pupil_plane_size and
    # relatively large pupil_plane_scale to speed up the unit test.
    atm._reset()
    assert atm[0]._time == 0.0, "Wrong time for AtmosphericScreen"
    kwargs = dict(exptime=0.05, time_step=0.01, diam=1.1, lam=1000.0)
    psf = atm.makePSF(**kwargs)
    check_pickle(psf)
    check_pickle(psf, func=lambda x:x.drawImage(nx=20, ny=20, scale=0.1))

    psf2 = atm2.makePSF(**kwargs)
    psf3 = atm3.makePSF(**kwargs)
    psf4 = atm4.makePSF(**kwargs)

    np.testing.assert_array_equal(psf, psf2, "PhaseScreenPSFs are inconsistent")
    np.testing.assert_array_equal(psf, psf3, "PhaseScreenPSFs are inconsistent")
    np.testing.assert_array_equal(psf, psf4, "PhaseScreenPSFs are inconsistent")

    # Check errors in u,v,t shapes.
    assert_raises(ValueError, ar1.wavefront, aper.u, aper.v[:-1,:-1])
    assert_raises(ValueError, ar1.wavefront, aper.u[:-1,:-1], aper.v)
    assert_raises(ValueError, ar1.wavefront, aper.u, aper.v, 0.1 * aper.u[:-1,:-1])
    assert_raises(ValueError, ar1.wavefront_gradient, aper.u, aper.v[:-1,:-1])
    assert_raises(ValueError, ar1.wavefront_gradient, aper.u[:-1,:-1], aper.v)
    assert_raises(ValueError, ar1.wavefront_gradient, aper.u, aper.v, 0.1 * aper.u[:-1,:-1])

    assert_raises(ValueError, ar3.wavefront, aper.u, aper.v[:-1,:-1])
    assert_raises(ValueError, ar3.wavefront, aper.u[:-1,:-1], aper.v)
    assert_raises(ValueError, ar3.wavefront_gradient, aper.u, aper.v[:-1,:-1])
    assert_raises(ValueError, ar3.wavefront_gradient, aper.u[:-1,:-1], aper.v)


@timer
def test_frozen_flow():
    """Test that frozen flow screen really is frozen, i.e., phase(x=0, t=0) == phase(x=v*t, t=t)."""
    rng = galsim.BaseDeviate(1234)
    vx = 1.0  # m/s
    t = 0.05  # s
    x = vx*t  # 0.05 m
    dx = x
    alt = x/1000   # -> 0.00005 km; silly example, but yields exact results...

    screen = galsim.AtmosphericScreen(1.0, dx, alt, vx=vx, rng=rng)
    aper = galsim.Aperture(diam=1, pupil_plane_size=20., pupil_plane_scale=20./dx)
    with assert_warns(galsim.GalSimWarning):
        # Warns about scale being too large, which we do on purpose to make the test faster.
        wf0 = screen.wavefront(aper.u, aper.v, None, theta0)
    dwdu0, dwdv0 = screen.wavefront_gradient(aper.u, aper.v, t=screen._time)
    screen._seek(t)
    assert screen._time == t, "Wrong time for AtmosphericScreen"
    wf1 = screen.wavefront(aper.u, aper.v, None, theta=(45*galsim.degrees, 0*galsim.degrees))
    dwdu1, dwdv1 = screen.wavefront_gradient(aper.u, aper.v, t=screen._time,
                                             theta=(45*galsim.degrees, 0*galsim.degrees))

    np.testing.assert_array_almost_equal(wf0, wf1, 5, "Flow is not frozen")
    np.testing.assert_array_almost_equal(dwdu0, dwdu1, 5, "Flow is not frozen")
    np.testing.assert_array_almost_equal(dwdv0, dwdv1, 5, "Flow is not frozen")

    # We should be able to rewind too.
    screen._seek(0.01)
    np.testing.assert_allclose(screen._time, 0.01, err_msg="Wrong time for AtmosphericScreen")
    wf2 = screen.wavefront(aper.u, aper.v, 0.0)
    np.testing.assert_array_almost_equal(wf0, wf2, 5, "Flow is not frozen")


@timer
def test_phase_psf_reset():
    """Test that phase screen reset() method correctly resets the screen to t=0."""
    rng = galsim.BaseDeviate(1234)
    # Test frozen AtmosphericScreen first
    atm = galsim.Atmosphere(screen_size=30.0, altitude=10.0, speed=0.1, alpha=1.0, rng=rng)
    aper = galsim.Aperture(diam=1.0, lam=500.0)
    wf2 = atm.wavefront(aper.u, aper.v, 0.0, theta0)
    wf1 = atm._wavefront(aper.u, aper.v, None, theta0)
    assert np.all(wf1 == wf2)

    atm._seek(1.0)
    wf4 = atm.wavefront(aper.u, aper.v, 1.0, theta0)
    wf3 = atm._wavefront(aper.u, aper.v, None, theta0)
    assert np.all(wf3 == wf4)

    # Verify that atmosphere did advance
    assert not np.all(wf1 == wf3)

    # Now verify that reset brings back original atmosphere
    atm._reset()
    wf3 = atm._wavefront(aper.u, aper.v, None, theta0)
    np.testing.assert_array_equal(wf1, wf3, "Phase screen didn't reset")

    # Now check with boiling, but no wind.
    atm = galsim.Atmosphere(screen_size=30.0, altitude=10.0, alpha=0.997, time_step=0.01, rng=rng)
    atm.instantiate()
    wf1 = atm._wavefront(aper.u, aper.v, None, theta0)
    atm._seek(0.1)
    wf2 = atm._wavefront(aper.u, aper.v, None, theta0)
    # Verify that atmosphere did advance
    assert not np.all(wf1 == wf2)

    # Now verify that reset brings back original atmosphere
    atm._reset()
    wf3 = atm._wavefront(aper.u, aper.v, None, theta0)
    np.testing.assert_array_equal(wf1, wf3, "Phase screen didn't reset")


@timer
def test_phase_psf_batch():
    """Test that PSFs generated and drawn serially match those generated and drawn in batch."""
    import time
    NPSFs = 10
    exptime = 0.3
    rng = galsim.BaseDeviate(1234)
    atm = galsim.Atmosphere(screen_size=10.0, altitude=10.0, alpha=0.997, time_step=0.01, rng=rng)
    theta = [(i*galsim.arcsec, i*galsim.arcsec) for i in range(NPSFs)]

    kwargs = dict(lam=1000.0, exptime=exptime, diam=1.0)

    t1 = time.time()
    psfs = [atm.makePSF(theta=th, **kwargs) for th in theta]
    imgs = [psf.drawImage() for psf in psfs]
    print('time for {0} PSFs in batch: {1:.2f} s'.format(NPSFs, time.time() - t1))

    t2 = time.time()
    more_imgs = []
    for th in theta:
        psf = atm.makePSF(theta=th, **kwargs)
        more_imgs.append(psf.drawImage())
    print('time for {0} PSFs in serial: {1:.2f} s'.format(NPSFs, time.time() - t2))

    for img1, img2 in zip(imgs, more_imgs):
        np.testing.assert_array_equal(
            img1, img2,
            "Individually generated AtmosphericPSF differs from AtmosphericPSF generated in batch")


@timer
def test_opt_indiv_aberrations():
    """Test that aberrations specified by name match those specified in `aberrations` list."""
    screen1 = galsim.OpticalScreen(diam=4.0, tip=0.2, tilt=0.3, defocus=0.4, astig1=0.5, astig2=0.6,
                                   coma1=0.7, coma2=0.8, trefoil1=0.9, trefoil2=1.0, spher=1.1)
    screen2 = galsim.OpticalScreen(diam=4.0, aberrations=[0.0, 0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7,
                                                          0.8, 0.9, 1.0, 1.1])

    psf1 = galsim.PhaseScreenList(screen1).makePSF(diam=4.0, lam=500.0)
    psf2 = galsim.PhaseScreenList(screen2).makePSF(diam=4.0, lam=500.0)

    np.testing.assert_array_equal(
            psf1._img, psf2._img,
            "Individually specified aberrations differs from aberrations specified as list.")


@timer
def test_scale_unit():
    """Test that `scale_unit` keyword correctly sets the units for PhaseScreenPSF."""
    aper = galsim.Aperture(diam=1.0)
    rng = galsim.BaseDeviate(1234)
    # Test frozen AtmosphericScreen first
    atm = galsim.Atmosphere(screen_size=30.0, altitude=10.0, speed=0.1, alpha=1.0, rng=rng)
    psf = galsim.PhaseScreenPSF(atm, 500.0, aper=aper, scale_unit=galsim.arcsec)
    im1 = psf.drawImage(nx=32, ny=32, scale=0.1, method='no_pixel')
    psf2 = galsim.PhaseScreenPSF(atm, 500.0, aper=aper, scale_unit='arcmin')
    im2 = psf2.drawImage(nx=32, ny=32, scale=0.1/60.0, method='no_pixel')
    np.testing.assert_almost_equal(
            im1.array, im2.array, 8,
            'PhaseScreenPSF inconsistent use of scale_unit')

    opt_psf1 = galsim.OpticalPSF(lam=500.0, diam=1.0, scale_unit=galsim.arcsec)
    opt_psf2 = galsim.OpticalPSF(lam=500.0, diam=1.0, scale_unit='arcsec')
    assert opt_psf1 == opt_psf2, "scale unit did not parse as string"

    assert_raises(ValueError, galsim.OpticalPSF, lam=500.0, diam=1.0, scale_unit='invalid')
    assert_raises(ValueError, galsim.PhaseScreenPSF, atm, 500.0, aper=aper, scale_unit='invalid')
    # Check a few other construction errors now too.
    assert_raises(ValueError, galsim.PhaseScreenPSF, atm, 500.0, scale_unit='arcmin')
    assert_raises(TypeError, galsim.PhaseScreenPSF, atm, 500.0, aper=aper, theta=34.*galsim.degrees)
    assert_raises(TypeError, galsim.PhaseScreenPSF, atm, 500.0, aper=aper, theta=(34, 5))
    assert_raises(ValueError, galsim.PhaseScreenPSF, atm, 500.0, aper=aper, exptime=-1)

@timer
def test_flux():
    """Test setting the `flux` to non-unity.
    """
    aper = galsim.Aperture(diam=1.0)
    rng = galsim.BaseDeviate(1234)
    # Test frozen AtmosphericScreen first
    atm = galsim.Atmosphere(screen_size=30.0, altitude=10.0, speed=0.1, alpha=1.0, rng=rng)
    for flux in [1.6, 0.02, -17]:
        psf1 = galsim.PhaseScreenPSF(atm, 500.0, aper=aper, flux=flux)
        im = psf1.drawImage(nx=32, ny=32, scale=0.5)
        print('flux = ',flux,' image sum = ',np.sum(im.array))
        np.testing.assert_allclose(np.sum(im.array), flux, rtol=1.e-3)
        check_basic(psf1, 'PhaseScreenPSF with flux=%f'%flux, approx_maxsb=True)

        psf2 = galsim.PhaseScreenPSF(atm, 500.0, aper=aper).withFlux(flux)
        assert psf2 == psf1

        gsp = galsim.GSParams(maximum_fft_size=4096)
        psf3 = galsim.OpticalPSF(lam=500.0, diam=0.9, flux=flux, gsparams=gsp)
        psf3.drawImage(im)
        print('flux = ',flux,' image sum = ',np.sum(im.array))
        np.testing.assert_allclose(np.sum(im.array), flux, rtol=1.e-3)
        check_basic(psf3, 'OpticalPSF with flux=%f'%flux, approx_maxsb=True)

        psf4 = galsim.OpticalPSF(lam=500.0, diam=0.9, gsparams=gsp).withFlux(flux)
        assert psf4 == psf3

    with assert_raises(galsim.GalSimValueError):
        psf = galsim.PhaseScreenPSF(atm, 500.0, aper=aper, flux=0.)
        im = psf.drawImage(nx=256, ny=256, scale=0.3)

    with assert_raises(galsim.GalSimValueError):
        psf = galsim.PhaseScreenPSF(atm, 500.0, aper=aper, fft_sign=0)

    psf = galsim.PhaseScreenPSF(atm, 500.0, aper=aper)
    assert psf.fft_sign == '+'
    psf = galsim.PhaseScreenPSF(atm, 500.0, aper=aper, fft_sign='-')
    assert psf.fft_sign == '-'


@timer
def test_stepk_maxk():
    """Test options to specify (or not) stepk and maxk.
    """
    # Make a dummy Kolmogorov just in case this test is the first to do so.  Don't want the
    # building of the KolmogorovInfo lookup table to mess up the timing test.
    kolm = galsim.Kolmogorov(fwhm=2)
    kolm._sbp

    import time
    aper = galsim.Aperture(diam=1.0)
    rng = galsim.BaseDeviate(123456)
    # Test frozen AtmosphericScreen first
    atm = galsim.Atmosphere(screen_size=30.0, altitude=10.0, speed=0.1, alpha=1.0, rng=rng)
    psf = galsim.PhaseScreenPSF(atm, 500.0, aper=aper, scale_unit=galsim.arcsec)

    t0 = time.time()
    stepk1 = psf.stepk
    maxk1 = psf.maxk
    t1 = time.time()
    print('stepk1 = ',stepk1)
    print('maxk1 = ',maxk1)
    print('t1 = ',t1-t0)

    psf._prepareDraw()
    stepk2 = psf.stepk
    maxk2 = psf.maxk
    t2 = time.time()
    print('stepk2 = ',stepk2)
    print('maxk2 = ',maxk2)
    print('goodImageSize = ',psf.getGoodImageSize(0.2))
    print('t2 = ',t2-t1)

    np.testing.assert_allclose(stepk1, stepk2, rtol=0.07)
    np.testing.assert_allclose(maxk1, maxk2, rtol=0.05)

    # Also make sure that prepareDraw wasn't called to calculate the first one.
    # Should be very quick to do the first stepk, maxk, but slow to do the second.
    assert t1-t0 < t2-t1

    # Check that stepk changes when gsparams.folding_threshold become more extreme.
    # (Note: maxk is independent of maxk_threshold because of the hard edge of the aperture.)
    gsp = galsim.GSParams(folding_threshold=1.e-3, maxk_threshold=1.e-4)
    psf1 = galsim.PhaseScreenPSF(atm, 500.0, diam=1.0, scale_unit=galsim.arcsec, gsparams=gsp)
    stepk3 = psf1.stepk
    maxk3 = psf1.maxk
    print('stepk3 = ',stepk3)
    print('maxk3 = ',maxk3)
    print('goodImageSize = ',psf1.getGoodImageSize(0.2))
    assert stepk3 < stepk1
    assert maxk3 == maxk1

    psf2 = psf.withGSParams(gsp)
    assert psf2.gsparams == gsp
    assert psf2 != psf
    assert psf2 == psf1
    assert psf2.aper.gsparams == gsp
    assert psf.aper.gsparams != gsp
    assert psf1 == psf.withGSParams(folding_threshold=1.e-3, maxk_threshold=1.e-4)

    aper3 = galsim.Aperture(diam=1.0, gsparams=gsp)
    psf3 = galsim.PhaseScreenPSF(atm, 500.0, aper=aper3, scale_unit=galsim.arcsec)
    assert psf3.gsparams == gsp
    assert psf3 != psf
    assert psf3 == psf1

    # Check that it respects the force_stepk and force_maxk parameters
    psf2 = galsim.PhaseScreenPSF(atm, 500.0, aper=aper, scale_unit=galsim.arcsec,
                                 _force_stepk=stepk2/1.5, _force_maxk=maxk2*2.0)
    np.testing.assert_almost_equal(
            psf2.stepk, stepk2/1.5, decimal=7,
            err_msg="PhaseScreenPSF did not adopt forced value for stepk")
    np.testing.assert_almost_equal(
            psf2.maxk, maxk2*2.0, decimal=7,
            err_msg="PhaseScreenPSF did not adopt forced value for maxk")
    check_pickle(psf)
    check_pickle(psf2)

    # Try out non-geometric-shooting
    psf3 = atm.makePSF(lam=500.0, aper=aper, geometric_shooting=False)
    img = galsim.Image(32, 32, scale=0.2)
    do_shoot(psf3, img, "PhaseScreenPSF")
    # Also make sure a few other methods at least run
    psf3.centroid
    psf3.max_sb

    # If we force stepk very low, it will trigger a warning when we try to draw it.
    psf4 = galsim.PhaseScreenPSF(atm, 500.0, aper=aper, scale_unit=galsim.arcsec,
                                 _force_stepk=stepk2/3.5)
    with assert_warns(galsim.GalSimWarning):
        psf4._prepareDraw()
        psf4._ii  # Don't need to actually draw it.  Just access this attribute.

    # Can suppress this warning if desired.
    psf5 = galsim.PhaseScreenPSF(atm, 500.0, aper=aper, scale_unit=galsim.arcsec,
                                 _force_stepk=stepk2/3.5, suppress_warning=True)
    with assert_raises(AssertionError):
        with assert_warns(galsim.GalSimWarning):
            psf5._prepareDraw()


@timer
def test_ne():
    """Test Apertures, PhaseScreens, PhaseScreenLists, and PhaseScreenPSFs for not-equals."""
    pupil_plane_im = galsim.fits.read(os.path.join(imgdir, pp_file))

    # Test galsim.Aperture __ne__
    objs = [galsim.Aperture(diam=1.0),
            galsim.Aperture(diam=1.1),
            galsim.Aperture(diam=1.0, oversampling=1.5),
            galsim.Aperture(diam=1.0, pad_factor=1.5),
            galsim.Aperture(diam=1.0, circular_pupil=False),
            galsim.Aperture(diam=1.0, obscuration=0.3),
            galsim.Aperture(diam=1.0, nstruts=3),
            galsim.Aperture(diam=1.0, nstruts=3, strut_thick=0.2),
            galsim.Aperture(diam=1.0, nstruts=3, strut_angle=15*galsim.degrees),
            galsim.Aperture(diam=1.0, pupil_plane_im=pupil_plane_im),
            galsim.Aperture(diam=1.0, pupil_plane_im=pupil_plane_im,
                            pupil_angle=10.0*galsim.degrees)]
    check_all_diff(objs)

    # Test AtmosphericScreen __ne__
    rng = galsim.BaseDeviate(1)
    objs = [galsim.AtmosphericScreen(10.0, rng=rng),
            galsim.AtmosphericScreen(1.0, rng=rng),
            galsim.AtmosphericScreen(10.0, rng=rng, vx=1.0),
            galsim.AtmosphericScreen(10.0, rng=rng, vy=1.0),
            galsim.AtmosphericScreen(10.0, rng=rng, alpha=0.999, time_step=0.01),
            galsim.AtmosphericScreen(10.0, rng=rng, altitude=1.0),
            galsim.AtmosphericScreen(10.0, rng=rng, alpha=0.999, time_step=0.02),
            galsim.AtmosphericScreen(10.0, rng=rng, alpha=0.998, time_step=0.02),
            galsim.AtmosphericScreen(10.0, rng=rng, r0_500=0.1),
            galsim.AtmosphericScreen(10.0, rng=rng, L0=10.0),
            galsim.AtmosphericScreen(10.0, rng=rng, vx=10.0),
            ]
    check_all_diff(objs)
    objs.append(galsim.AtmosphericScreen(10.0, rng=rng))
    objs[-1].instantiate()
    # Should still all be __ne__, but first and last will have the same hash this time.
    assert hash(objs[0]) == hash(objs[-1])
    check_all_diff(objs, check_hash=False)

    # Test OpticalScreen __ne__
    objs = [galsim.OpticalScreen(diam=1.0),
            galsim.OpticalScreen(diam=1.0, tip=1.0),
            galsim.OpticalScreen(diam=1.0, tilt=1.0),
            galsim.OpticalScreen(diam=1.0, defocus=1.0),
            galsim.OpticalScreen(diam=1.0, astig1=1.0),
            galsim.OpticalScreen(diam=1.0, astig2=1.0),
            galsim.OpticalScreen(diam=1.0, coma1=1.0),
            galsim.OpticalScreen(diam=1.0, coma2=1.0),
            galsim.OpticalScreen(diam=1.0, trefoil1=1.0),
            galsim.OpticalScreen(diam=1.0, trefoil2=1.0),
            galsim.OpticalScreen(diam=1.0, spher=1.0),
            galsim.OpticalScreen(diam=1.0, spher=1.0, lam_0=100.0),
            galsim.OpticalScreen(diam=1.0, aberrations=[0,0,1.1]), # tip=1.1
            ]
    check_all_diff(objs)

    # Test PhaseScreenList __ne__
    atm = galsim.Atmosphere(10.0, vx=1.0)
    objs = [galsim.PhaseScreenList(atm),
            galsim.PhaseScreenList(objs),  # Reuse list of OpticalScreens above
            galsim.PhaseScreenList(objs[0:2])]
    check_all_diff(objs)

    # Test PhaseScreenPSF __ne__
    psl = galsim.PhaseScreenList(atm)
    objs = [galsim.PhaseScreenPSF(psl, 500.0, exptime=0.03, diam=1.0)]
    objs += [galsim.PhaseScreenPSF(psl, 700.0, exptime=0.03, diam=1.0)]
    objs += [galsim.PhaseScreenPSF(psl, 700.0, exptime=0.03, diam=1.0, fft_sign='-')]
    objs += [galsim.PhaseScreenPSF(psl, 700.0, exptime=0.03, diam=1.1)]
    objs += [galsim.PhaseScreenPSF(psl, 700.0, exptime=0.03, diam=1.0, flux=1.1)]
    objs += [galsim.PhaseScreenPSF(psl, 700.0, exptime=0.03, diam=1.0, interpolant='linear')]
    stepk = objs[0].stepk
    maxk = objs[0].maxk
    objs += [galsim.PhaseScreenPSF(psl, 700.0, exptime=0.03, diam=1.0, _force_stepk=stepk/1.5)]
    objs += [galsim.PhaseScreenPSF(psl, 700.0, exptime=0.03, diam=1.0, _force_maxk=maxk*2.0)]
    check_all_diff(objs)


@timer
def test_phase_gradient_shoot(run_slow):
    """Test that photon-shooting PSFs match Fourier optics PSFs when using the same phase screens,
    and also match the expected size from an analytic VonKarman-convolved-with-Airy PSF.
    """
    # Make the atmosphere
    seed = 12345
    r0_500 = 0.15  # m
    L0 = 20.0  # m
    nlayers = 6
    screen_size = 102.4  # m

    # Ideally, we'd use as small a screen scale as possible here.  The runtime for generating
    # phase screens scales like `screen_scale`^-2 though, which is pretty steep, so we use a larger-
    # than-desireable scale for the not run_slow branch.  This is known to lead to a bias
    # in PSF size, which we attempt to account for below when actually comparing FFT PSF moments to
    # photon-shooting PSF moments.  Note that we don't need to apply such a correction when
    # comparing the photon-shooting PSF to the analytic VonKarman PSF since these both avoid the
    # screen_scale problem to begin with.  (Even though we do generate screens for the
    # photon-shooting PSF, because we truncate the power spectrum above kcrit, we don't require as
    # high of resolution).
    if run_slow:
        screen_scale = 0.025 # m
    else:
        screen_scale = 0.1 # m
    max_speed = 20  # m/s

    rng = galsim.BaseDeviate(seed)
    u = galsim.UniformDeviate(rng)

    # Use atmospheric weights from 1998 Gemini site selection process as something reasonably
    # realistic.  (Ellerbroek 2002, JOSA Vol 19 No 9).
    Ellerbroek_alts = [0.0, 2.58, 5.16, 7.73, 12.89, 15.46]  # km
    Ellerbroek_weights = [0.652, 0.172, 0.055, 0.025, 0.074, 0.022]
    Ellerbroek_interp = galsim.LookupTable(
            Ellerbroek_alts,
            Ellerbroek_weights,
            interpolant='linear')
    alts = np.max(Ellerbroek_alts)*np.arange(nlayers)/(nlayers-1)
    weights = Ellerbroek_interp(alts)
    weights /= sum(weights)

    spd = []  # Wind speed in m/s
    dirn = [] # Wind direction in radians
    r0_500s = [] # Fried parameter in m at a wavelength of 500 nm.
    for i in range(nlayers):
        spd.append(u()*max_speed)
        dirn.append(u()*360*galsim.degrees)
        r0_500s.append(r0_500*weights[i]**(-3./5))
    rng2 = rng.duplicate()
    atm = galsim.Atmosphere(r0_500=r0_500, L0=L0, speed=spd, direction=dirn, altitude=alts, rng=rng,
                            screen_size=screen_size, screen_scale=screen_scale)
    # Make a second atmosphere to use for geometric photon-shooting
    atm2 = galsim.Atmosphere(r0_500=r0_500, L0=L0, speed=spd, direction=dirn, altitude=alts,
                             rng=rng2, screen_size=screen_size, screen_scale=screen_scale)
    # These should be equal at the moment, before we've actually instantiated any screens by drawing
    # with them.
    assert atm == atm2

    lam = 500.0
    diam = 4.0
    pad_factor = 0.5
    oversampling = 0.5

    aper = galsim.Aperture(diam=diam, lam=lam,
                           screen_list=atm, pad_factor=pad_factor,
                           oversampling=oversampling)

    xs = np.empty((10,), dtype=float)
    ys = np.empty((10,), dtype=float)
    u.generate(xs)
    u.generate(ys)
    thetas = [(x*galsim.degrees, y*galsim.degrees) for x, y in zip(xs, ys)]

    if run_slow:
        exptime = 15.0
        time_step = 0.05
        centroid_tolerance = 0.08
        size_tolerance = 0.06  # absolute
        size_bias = 0.015  # as a fraction
        shape_tolerance = 0.01
    else:
        exptime = 1.0
        time_step = 0.1
        centroid_tolerance = 0.3
        size_tolerance = 0.3
        size_bias = 0.15
        shape_tolerance = 0.04
    t0 = 0.0

    psfs = [
        atm.makePSF(
            lam, diam=diam, theta=th, t0=t0, exptime=exptime, aper=aper,
            fft_sign='+' if i%2 else '-'  # Test both possibilities
        )
        for i, th in enumerate(thetas)
    ]
    psfs2 = [
        atm2.makePSF(
            lam, diam=diam, theta=th, t0=t0, exptime=exptime, aper=aper, time_step=time_step,
            fft_sign='+' if i%2 else '-'
        )
        for i, th in enumerate(thetas)
    ]
    shoot_moments = []
    fft_moments = []

    vk = galsim.VonKarman(lam=lam, r0=r0_500*(lam/500)**1.2, L0=L0)
    airy = galsim.Airy(lam=lam, diam=diam)
    obj = galsim.Convolve(vk, airy)
    vkImg = obj.drawImage(nx=256, ny=256, scale=0.05)
    vkMom = galsim.hsm.FindAdaptiveMom(vkImg)

    for psf, psf2 in zip(psfs, psfs2):
        rng1 = rng.duplicate()  # Save for later.
        im_shoot = psf.drawImage(nx=256, ny=256, scale=0.05, method='phot', n_photons=100000,
                                 rng=rng)
        im_fft = psf2.drawImage(nx=256, ny=256, scale=0.05)

        # at this point, the atms should be different.
        assert atm != atm2

        shoot_moment = galsim.hsm.FindAdaptiveMom(im_shoot)
        fft_moment = galsim.hsm.FindAdaptiveMom(im_fft)

        print()
        print()
        print()
        print(shoot_moment.observed_shape.g1)
        print(fft_moment.observed_shape.g1)

        # import matplotlib.pyplot as plt
        # fig, axes = plt.subplots(ncols=2)
        # axes[0].imshow(im_shoot.array)
        # axes[1].imshow(im_fft.array)
        # plt.show()

        np.testing.assert_allclose(
            shoot_moment.moments_centroid.x,
            fft_moment.moments_centroid.x,
            rtol=0, atol=centroid_tolerance,
            err_msg='Phase gradient centroid x not close to fft centroid')

        np.testing.assert_allclose(
            shoot_moment.moments_centroid.y,
            fft_moment.moments_centroid.y,
            rtol=0, atol=centroid_tolerance,
            err_msg='Phase gradient centroid y not close to fft centroid')

        print('shoot_moment sigma = ',shoot_moment.moments_sigma)
        print('fft_moment sigma = ',fft_moment.moments_sigma)
        print('biased fft_moment sigma = ',fft_moment.moments_sigma * (1+size_bias))
        np.testing.assert_allclose(
            shoot_moment.moments_sigma,
            fft_moment.moments_sigma*(1+size_bias),
            rtol=0, atol=size_tolerance,
            err_msg='Phase gradient sigma not close to fft sigma')

        np.testing.assert_allclose(
            shoot_moment.moments_sigma,
            vkMom.moments_sigma,
            rtol=0.1, atol=0,
            err_msg='Phase gradient sigma not close to infinite exposure analytic sigma'
        )

        np.testing.assert_allclose(
            shoot_moment.observed_shape.g1,
            fft_moment.observed_shape.g1,
            rtol=0, atol=shape_tolerance,
            err_msg='Phase gradient shape g1 not close to fft shape')

        np.testing.assert_allclose(
            shoot_moment.observed_shape.g2,
            fft_moment.observed_shape.g2,
            rtol=0, atol=shape_tolerance,
            err_msg='Phase gradient shape g2 not close to fft shape')

        shoot_moments.append(shoot_moment)
        fft_moments.append(fft_moment)

        # Check the flux
        # The Airy part sends a lot of flux off the edge, so this test is pretty loose.
        added_flux = im_shoot.added_flux
        print('psf.flux = ',psf.flux, added_flux, im_shoot.array.sum())
        assert np.isclose(added_flux, psf.flux, rtol=1.e-3)
        assert np.isclose(im_shoot.array.sum(), psf.flux, rtol=1.e-3)

        # Check doing this with photon_ops
        im_shoot2 = galsim.DeltaFunction().drawImage(nx=256, ny=256, scale=0.05, method='phot',
                                                     n_photons=100000, rng=rng1.duplicate(),
                                                     photon_ops=[psf])
        np.testing.assert_allclose(im_shoot2.array, im_shoot.array)

        # Repeat with the pupil_sampler, time_sampler before the psf.
        pupil_sampler = galsim.PupilImageSampler(diam=diam, lam=lam,
                                                 pad_factor=pad_factor,
                                                 oversampling=oversampling,
                                                 screen_list=atm)
        time_sampler = galsim.TimeSampler(t0=t0, exptime=exptime)
        im_shoot3 = galsim.DeltaFunction().drawImage(nx=256, ny=256, scale=0.05, method='phot',
                                                     n_photons=100000, rng=rng1.duplicate(),
                                                     photon_ops=[pupil_sampler, time_sampler, psf])
        np.testing.assert_allclose(im_shoot3.array, im_shoot.array)

        check_pickle(pupil_sampler)

        # Quick check with PupilAnnulusSampler
        pupil_sampler2 = galsim.PupilAnnulusSampler(R_outer=diam/2)
        im_shoot4 = galsim.DeltaFunction().drawImage(nx=256, ny=256, scale=0.05, method='phot',
                                                     n_photons=100000, rng=rng1,
                                                     photon_ops=[pupil_sampler2, psf]
        )
        shoot_moment4 = galsim.hsm.FindAdaptiveMom(im_shoot4)

        np.testing.assert_allclose(
            shoot_moment4.moments_sigma,
            shoot_moment.moments_sigma,
            rtol=0, atol=0.05,
            err_msg='Annulus sampling not close to image sampling'
        )

        check_pickle(pupil_sampler2)

    # I cheated.  Here's code to evaluate how small I could potentially set the tolerances above.
    # I think they're all fine, but this is admittedly a tad bit backwards.
    best_size_bias = np.mean([s1.moments_sigma/s2.moments_sigma
                              for s1, s2 in zip(shoot_moments, fft_moments)])
    print("best_size_bias = ", best_size_bias)
    print("xcentroid")
    print(max(np.abs([s1.moments_centroid.x - s2.moments_centroid.x
                      for s1, s2 in zip(shoot_moments, fft_moments)])))
    print("ycentroid")
    print(max(np.abs([s1.moments_centroid.y - s2.moments_centroid.y
                      for s1, s2 in zip(shoot_moments, fft_moments)])))
    print("size")
    print(max(np.abs([s1.moments_sigma - s2.moments_sigma*(1+size_bias)
                      for s1, s2 in zip(shoot_moments, fft_moments)])))
    print("bestsize")
    print(max(np.abs([s1.moments_sigma - s2.moments_sigma*(best_size_bias)
                      for s1, s2 in zip(shoot_moments, fft_moments)])))
    print("g1")
    print(max(np.abs([s1.observed_shape.g1 - s2.observed_shape.g1
                      for s1, s2 in zip(shoot_moments, fft_moments)])))
    print("g2")
    print(max(np.abs([s1.observed_shape.g2 - s2.observed_shape.g2
                      for s1, s2 in zip(shoot_moments, fft_moments)])))

    # import matplotlib.pyplot as plt
    # fig, ax = plt.subplots(nrows=1, ncols=1)
    # ax.scatter(
    #     [s.observed_shape.g1 for s in shoot_moments],
    #     [s.observed_shape.g1 for s in fft_moments]
    # )
    # xlim = ax.get_xlim()
    # ylim = ax.get_ylim()
    # lim = (min(xlim[0], ylim[0]), max(xlim[1], ylim[1]))
    # ax.set_xlim(lim)
    # ax.set_ylim(lim)
    # ax.plot([-100, 100], [-100, 100])
    # plt.show()

    # Verify that shoot with rng=None runs
    psf.shoot(100, rng=None)

    # Check that second_kick=False and second_kick=GSObject also run, and that we can shoot
    # photons with these settings.
    for second_kick in [False, galsim.Gaussian(fwhm=1)]:
        psf = atm.makePSF(lam=500.0, exptime=10, aper=aper, second_kick=second_kick)
        assert psf.second_kick == second_kick
        img = psf.drawImage(nx=64, ny=64, scale=0.1, method='phot', n_photons=100)

    # Verify that we can phase_gradient_shoot with 0 or 1 photons.
    psf.shoot(0)
    psf.shoot(1)


@timer
def test_input():
    """Check that exceptions are raised for invalid input"""
    # Specifying only one of alpha and time_step is an error.
    assert_raises(ValueError, galsim.AtmosphericScreen, screen_size=10.0, time_step=0.01)
    assert_raises(ValueError, galsim.AtmosphericScreen, screen_size=10.0, alpha=0.997)
    # But specifying both is alright.
    galsim.AtmosphericScreen(screen_size=10.0, alpha=0.997, time_step=0.01)

    # Try some variations for Atmosphere
    assert_raises(ValueError, galsim.Atmosphere,
                  screen_size=10.0, altitude=[0., 1.],
                  r0_500=[0.2, 0.3, 0.2])
    assert_raises(ValueError, galsim.Atmosphere,
                  screen_size=10.0, r0_500=[0.4, 0.4, 0.4],
                  r0_weights=[0.1, 0.3, 0.6])


@timer
def test_r0_weights():
    """Check that r0_weights functions as expected."""
    r0_500 = 0.2

    # Check that reassembled net r0_500 matches input
    atm = galsim.Atmosphere(screen_size=10.0, altitude=[0,1,2,3], r0_500=r0_500)
    r0s = [screen.r0_500 for screen in atm]
    np.testing.assert_almost_equal(np.sum([r0**(-5./3) for r0 in r0s])**(-3./5), r0_500)
    np.testing.assert_almost_equal(atm.r0_500_effective, r0_500)

    # Check that old manual calculation matches automatic calculation inside Atmosphere()
    weights = [1, 2, 3, 4]
    normalized_weights = np.array(weights, dtype=float)/np.sum(weights)
    r0s_ref = [r0_500 * w**(-3./5) for w in normalized_weights]
    atm = galsim.Atmosphere(screen_size=10.0, altitude=[0,1,2,3], r0_500=r0_500, r0_weights=weights)
    r0s_test = [screen.r0_500 for screen in atm]
    np.testing.assert_almost_equal(r0s_test, r0s_ref)
    np.testing.assert_almost_equal(np.sum([r0**(-5./3) for r0 in r0s_test])**(-3./5), r0_500)
    np.testing.assert_almost_equal(atm.r0_500_effective, r0_500)


@timer
def test_speedup():
    """Make sure that photon-shooting a PhaseScreenPSF with geometric approximation yields
    significant speedup.
    """
    import time
    atm = galsim.Atmosphere(screen_size=10.0, altitude=[0,1,2,3], r0_500=0.2)
    # Should be ~seconds if _prepareDraw() gets executed, ~0.01s otherwise.
    psf = atm.makePSF(lam=500.0, diam=1.0, exptime=15.0, time_step=0.025)
    # Draw once to instantiate the SecondKick
    psf.drawImage(method='phot', n_photons=1e3)
    t0 = time.time()
    # Draw again for actual test
    psf.drawImage(method='phot', n_photons=1e3)
    t1 = time.time()
    print("Time for geometric approximation draw: {:6.4f}s".format(t1-t0))
    if test_timing:
        assert (t1-t0) < 0.1, "Photon-shooting took too long ({0} s).".format(t1-t0)


@timer
def test_instantiation_check():
    """Check that after instantiating, drawing with the other method will emit a warning.
    """
    atm1 = galsim.Atmosphere(screen_size=10.0, altitude=10, r0_500=0.2)
    psf1 = atm1.makePSF(lam=500.0, diam=1.0)
    psf1.drawImage()
    with assert_warns(galsim.GalSimWarning):
        psf1.drawImage(method='phot', n_photons=10)

    atm2 = galsim.Atmosphere(screen_size=10.0, altitude=10, r0_500=0.2)
    psf2 = atm2.makePSF(lam=500.0, diam=1.0)  # exptime = 0, so reasonable to draw w/ FFT
    psf2.drawImage(method='phot', n_photons=10)
    with assert_warns(galsim.GalSimWarning):
        psf2.drawImage()


@timer
def test_gc():
    """Make sure that pending psfs don't leak memory.
    """
    import gc
    # The below check about this may fail if some other test using PhaseScreenPSFs has failed.
    # To avoid this spurious double error, only do the below check if we start out with
    # nothing in the garbage collector.
    galsim.ChromaticConvolution._effective_prof_cache.clear()
    gc.collect()
    already_in_gc = any([isinstance(it, galsim.phase_psf.PhaseScreenPSF) for it in gc.get_objects()])

    atm = galsim.Atmosphere(screen_size=10.0, altitude=0, r0_500=0.15, suppress_warning=True)

    # First check that no PhaseScreenPSFs are known to the garbage collector
    assert not any([isinstance(it, galsim.phase_psf.PhaseScreenPSF) for it in gc.get_objects()])

    # Make a PhaseScreenPSF and check that it's known to the garbage collector
    psf = atm.makePSF(exptime=0.02, time_step=0.01, diam=1.1, lam=1000.0)
    assert any([isinstance(it, galsim.phase_psf.PhaseScreenPSF) for it in gc.get_objects()])

    # If we delete it, it disappears everywhere
    del psf
    gc.collect()
    assert not any([isinstance(it, galsim.phase_psf.PhaseScreenPSF) for it in gc.get_objects()])

    # If we draw one using photon-shooting, it still exists in _pending
    psf = atm.makePSF(exptime=0.02, time_step=0.01, diam=1.1, lam=1000.0)
    psf.drawImage(nx=10, ny=10, scale=0.2, method='phot', n_photons=100)
    assert psf in [p[1]() for p in atm._pending]

    # If we draw even one of many using fft, _pending gets completely emptied
    psf2 = atm.makePSF(exptime=0.02, time_step=0.01, diam=1.1, lam=1000.0)
    psf.drawImage(nx=10, ny=10, scale=0.2)
    assert atm._pending == []

    # And if then deleted, they again don't exist anywhere
    del psf, psf2
    gc.collect()
    if not already_in_gc:
        assert not any([isinstance(it, galsim.phase_psf.PhaseScreenPSF) for it in gc.get_objects()])

    # A corner case revealed in coverage tests:
    # Make sure that everything still works if some, but not all static pending PSFs are deleted.
    screen = galsim.OpticalScreen(diam=1.1)
    phaseScreenList = galsim.PhaseScreenList(screen)
    psf1 = phaseScreenList.makePSF(lam=1000.0, diam=1.1)
    psf2 = phaseScreenList.makePSF(lam=1000.0, diam=1.1)
    psf3 = phaseScreenList.makePSF(lam=1000.0, diam=1.1)
    del psf2
    psf1.drawImage(nx=10, ny=10, scale=0.2)
    del psf1, psf3
    assert phaseScreenList._pending == []
    gc.collect()
    if not already_in_gc:
        assert not any([isinstance(it, galsim.phase_psf.PhaseScreenPSF) for it in gc.get_objects()])


@timer
def test_withGSP():
    screen = galsim.phase_screens._DummyScreen(1.0, aberrations=[0,0,0,0,1])
    # Make sure screen really fails if we try to access _wavefront
    with np.testing.assert_raises(RuntimeError):
        screen._wavefront()
    psl = galsim.PhaseScreenList(screen)
    psf = psl.makePSF(exptime=0.02, time_step=0.01, diam=1.1, lam=1000.0)
    psfGSP = psf.withGSParams(folding_threshold=6e-3)
    psfGSP2 = psf.withGSParams(galsim.GSParams(folding_threshold=6e-3))
    assert psfGSP == psfGSP2
    # Don't worry about repr for DummyScreen
    check_pickle(psf, irreprable=True)
    check_pickle(psfGSP, irreprable=True)

    # We can't use check_pickle with func that involves a random number generator, so just hard-code
    # the equivalent here.
    try:
        import cPickle as pickle
    except:
        import pickle
    import copy
    copiers = [lambda x:pickle.loads(pickle.dumps(x)), copy.copy, copy.deepcopy]
    drawKwargs = dict(nx=32, ny=32, scale=0.2, method='phot', n_photons=10000)

    rng = galsim.BaseDeviate(57721)
    img = psf.drawImage(rng=rng, **drawKwargs)
    for copier in copiers:
        psf2 = copier(psf)
        assert psf2 is not psf
        rng = galsim.BaseDeviate(57721) # reset rng
        img2 = psf2.drawImage(rng=rng, **drawKwargs)
        assert img2 == img

    # Repeat but make a fresh (not previously drawn) source psf each time.  I.e.,
    # make sure that drawing and copy/pickling are commutative
    testimgs = []
    for copier in copiers:
        psf = psl.makePSF(exptime=0.02, time_step=0.01, diam=1.1, lam=1000.0)
        psf2 = copier(psf)
        assert psf2 is not psf
        rng = galsim.BaseDeviate(57721) # reset rng
        testimgs.append(psf2.drawImage(rng=rng, **drawKwargs))
    # Now draw the fresh psf and compare
    psf = psl.makePSF(exptime=0.02, time_step=0.01, diam=1.1, lam=1000.0)
    rng = galsim.BaseDeviate(57721)
    img = psf.drawImage(rng=rng, **drawKwargs)
    for testimg in testimgs:
        assert testimg == img

    # Want to check that copying and withGSParams are also commutative.  So repeat steps above
    # using psfGSP as the source/test.
    rng = galsim.BaseDeviate(57721)
    img = psfGSP.drawImage(rng=rng, **drawKwargs)  # uncopied withGSP img
    for copier in copiers:
        psf2 = copier(psfGSP)
        assert psf2 is not psfGSP
        rng = galsim.BaseDeviate(57721) # reset rng
        img2 = psf2.drawImage(rng=rng, **drawKwargs)  # this is a copy of a withGSP
        assert img2 == img

    # And finally, look at copies of undrawn withGSP PSFs.
    testimgs = []
    for copier in copiers:
        psf = psl.makePSF(exptime=0.02, time_step=0.01, diam=1.1, lam=1000.0)
        psfGSP = psf.withGSParams(folding_threshold=6e-3)  # hasn't been drawn yet
        psf2 = copier(psfGSP)  # copy of undrawn
        assert psf2 is not psfGSP
        rng = galsim.BaseDeviate(57721) # reset rng
        testimgs.append(psf2.drawImage(rng=rng, **drawKwargs))
    # Draw the (fresh) withGSP PSF and compare
    psf = psl.makePSF(exptime=0.02, time_step=0.01, diam=1.1, lam=1000.0)
    psfGSP = psf.withGSParams(folding_threshold=6e-3)
    rng = galsim.BaseDeviate(57721)
    img = psfGSP.drawImage(rng=rng, **drawKwargs)
    for testimg in testimgs:
        assert testimg == img

    # Also test OpticalPSF
    optPSF = galsim.OpticalPSF(lam=500, diam=1.0)
    optPSF2 = optPSF.withGSParams(folding_threshold=6e-3)
    assert isinstance(optPSF2, galsim.OpticalPSF)
    # And check that we really did get a different folding_threshold by comparing stepk and default
    # bounds
    assert optPSF.stepk != optPSF2.stepk
    assert optPSF.drawImage().bounds != optPSF2.drawImage().bounds


def dummyWork(i, atm):
    rng = galsim.UniformDeviate(i+10)
    theta = (rng()*galsim.degrees, rng()*galsim.degrees)
    psf = atm.makePSF(exptime=1.0, diam=1.1, lam=1000.0, theta=theta)
    return psf.drawImage(nx=32, ny=32, scale=0.2, n_photons=1000, method='phot', rng=rng)


@timer
def test_shared_memory(run_slow):
    """Test that shared memory hooks to AtmosphericScreen work.
    """
    import multiprocessing as mp
    # Make the atmosphere
    seed = 12345
    r0_500 = 0.15  # m
    L0 = 20.0  # m
    nlayers = 6
    screen_size = 102.4  # m
    screen_scale = 0.1 # m
    max_speed = 20  # m/s
    rng = galsim.BaseDeviate(seed)
    u = galsim.UniformDeviate(rng)
    Ellerbroek_alts = [0.0, 2.58, 5.16, 7.73, 12.89, 15.46]  # km
    Ellerbroek_weights = [0.652, 0.172, 0.055, 0.025, 0.074, 0.022]
    Ellerbroek_interp = galsim.LookupTable(
            Ellerbroek_alts,
            Ellerbroek_weights,
            interpolant='linear')
    alts = np.max(Ellerbroek_alts)*np.arange(nlayers)/(nlayers-1)
    weights = Ellerbroek_interp(alts)
    weights /= sum(weights)
    spd = []  # Wind speed in m/s
    dirn = [] # Wind direction in radians
    r0_500s = [] # Fried parameter in m at a wavelength of 500 nm.
    for i in range(nlayers):
        spd.append(u()*max_speed)
        dirn.append(u()*360*galsim.degrees)
        r0_500s.append(r0_500*weights[i]**(-3./5))

    if run_slow:
        ctxs = [None, mp.get_context("fork"), mp.get_context("spawn"), "forkserver"]
    else:
        ctxs = [None, mp.get_context("fork")]

    for ctx in ctxs:
        print('ctx = ',ctx)
        galsim.phase_screens.reset_shared_screens()

        atmPar = galsim.Atmosphere(
            r0_500=r0_500, L0=L0, speed=spd, direction=dirn, altitude=alts,
            rng=rng.duplicate(),
            screen_size=screen_size, screen_scale=screen_scale,
            mp_context=ctx)
        atmSer = galsim.Atmosphere(
            r0_500=r0_500, L0=L0, speed=spd, direction=dirn, altitude=alts,
            rng=rng.duplicate(),
            screen_size=screen_size, screen_scale=screen_scale,
            mp_context=ctx)
        # Add in an Optical Screen for good measure
        atmPar.append(galsim.OpticalScreen(diam=1.1))
        atmSer.append(galsim.OpticalScreen(diam=1.1))
        # make a dummy PSF so we can get kmax for screen instantiation
        psf = atmPar.makePSF(diam=1.1, lam=1000.0)
        kmax = psf.screen_kmax

        if ctx in (None, "forkserver"):
            Pool = mp.get_context(ctx).Pool
        else:
            Pool = ctx.Pool
        # See https://patchwork.ozlabs.org/project/gcc/patch/CAPJVwBkOF5GnrMr=4d1ehEKRGkY0tHzJzfXAYBguawu9y5wxXw@mail.gmail.com/#712883
        # for discussion about why this is recommended especially if in fork context and using
        # gcc compiler.
        with galsim.utilities.single_threaded():
            with Pool(None,
                    initializer=galsim.phase_screens.initWorker,
                    initargs=galsim.phase_screens.initWorkerArgs()
                    ) as pool:

                # Instantiate using the pool:
                atmPar.instantiate(pool=pool, kmax=kmax)

                resultsParallel = []
                for i in range(10):
                    resultsParallel.append(pool.apply_async(dummyWork, (i, atmPar)))
                for r in resultsParallel:
                    r.wait()
                resultsParallel = [r.get() for r in resultsParallel]

        # Serial comparison, also reinstantiate the atm here without using the pool
        atmSer.instantiate(pool=None, kmax=kmax)

        resultsSerial = []
        for i in range(10):
            resultsSerial.append(dummyWork(i, atmSer))

        assert resultsSerial == resultsParallel

        # Try to trigger both branches of inner instantiation check (after lock acquisition) by
        # using several processes at once to instantiate a single layer.  It's a race, and coverage
        # depends on when the apply_asyncs are actually started, so might not actually hit both
        # branches
        atm = galsim.Atmosphere(r0_500=r0_500, L0=L0, speed=spd, direction=dirn, altitude=alts,
                                rng=rng.duplicate(),
                                screen_size=screen_size, screen_scale=screen_scale,
                                mp_context=ctx)
        psf = atm.makePSF(diam=1.1, lam=1000.0)
        kmax = psf.screen_kmax
        with galsim.utilities.single_threaded():
            with Pool(None,
                    initializer=galsim.phase_screens.initWorker,
                    initargs=galsim.phase_screens.initWorkerArgs()
                    ) as pool:
                results = []
                for _ in range(10):
                    results.append(pool.apply_async(atm[0].instantiate, kwds={'kmax':kmax}))
                for r in results:
                    r.wait()

    ctx = mp.get_context("spawn")
    with assert_raises(galsim.GalSimNotImplementedError):
        atm = galsim.Atmosphere(
            screen_size=10.0, altitude=10.0, alpha=0.997, time_step=0.01, rng=rng,
            mp_context=ctx
        )

    # Atm ctor can't catch alpha != 1.0 error when trying to use shared memory with mp_context=None,
    # but initWorkerArgs can.
    atm = galsim.Atmosphere(screen_size=10.0, altitude=10.0, alpha=0.997, time_step=0.01, rng=rng)
    Pool = mp.get_context(None).Pool
    with assert_raises(galsim.GalSimNotImplementedError):
        pool = Pool(
            None,
            initializer=galsim.phase_screens.initWorker,
            initargs=galsim.phase_screens.initWorkerArgs()
        )


@timer
def test_pickle():
    # This is response to ImSim issue #234
    # https://github.com/LSSTDESC/imSim/issues/234

    # Pull out the relevant bits from the imsim code base.

    rng = galsim.BaseDeviate(1234)
    ud = galsim.UniformDeviate(rng)
    gd = galsim.GaussianDeviate(rng)

    altitudes = [0.0, 2.58, 5.16, 7.73, 12.89, 15.46]
    altitudes[0] = 0.2

    weights = [0.652, 0.172, 0.055, 0.025, 0.074, 0.022]
    weights = [np.abs(w*(1.0 + 0.1*gd())) for w in weights]
    weights = np.clip(weights, 0.01, 0.8)  # keep weights from straying too far.
    weights /= np.sum(weights)  # renormalize

    L0 = 0
    while L0 < 10.0 or L0 > 100:
        L0 = np.exp(gd() * 0.6 + np.log(25.0))
    r0_500 = 0.2

    L0 = [L0]*6

    maxSpeed = 20.0
    speeds = [ud()*maxSpeed for _ in range(6)]
    directions = [ud()*360.0*galsim.degrees for _ in range(6)]

    #screen_size = 819.2
    screen_size = 32
    screen_scale = 0.1

    import multiprocessing as mp
    ctxs = [None, mp.get_context("fork"), mp.get_context("spawn"), "forkserver"]

    for ctx in ctxs:
        kwargs = dict(r0_500=r0_500, L0=L0, speed=speeds, direction=directions,
                      altitude=altitudes, r0_weights=weights, rng=rng,
                      screen_size=screen_size, screen_scale=screen_scale, mp_context=ctx)
        atm = galsim.Atmosphere(**kwargs)

        xs = np.linspace(-1, 1, 10)
        ys = np.linspace(1, -1, 10)
        ts = np.linspace(0, 2, 10)
        wf = atm.wavefront(xs, ys, ts)

        pkl_file = 'output/atm_pickle_test.pkl'
        with open(pkl_file, 'wb') as fd:
            pickle.dump(atm, fd)

        with open(pkl_file, 'rb') as fd:
            atm2 = pickle.load(fd)
        assert atm2 == atm
        wf2 = atm2.wavefront(xs, ys, ts)
        np.testing.assert_equal(wf, wf2)

        # The above read works, but it relies on the objDict being in the _GSScreenShare directory.
        # Running this from a fresh program, it won't be in there yet.
        # For file persistence, we need to use the pickle_shared context manager

        # Write the psf + phase screen shared memory to disk
        pkl_file2 = 'output/atm_pickle_test2.pkl'
        with open(pkl_file2, 'wb') as fd:
            with galsim.utilities.pickle_shared():
                pickle.dump(atm, fd)

        # Simulate a new session by deleting atm and atm2, which should also clear out
        # _GSScreenShare
        del atm, atm2

        # Now if we read in pkl_file, it fails because __setstate__ can't find the required
        # screens.
        with assert_raises(KeyError):
            with open(pkl_file, 'rb') as fd:
                atm2 = pickle.load(fd)
            # XXX: The KeyError doesn't get raised in PyPy.  Not sure why.
            #      But this doesn't seem super critical, so rather than try to figure it out,
            #      I'm just punting on this and having PyPy go ahead and raise a KeyError.
            if 'PyPy' in sys.version:
                raise KeyError("PyPy workaround")

        # But we should be able to unpickle pkl_file2 since it includes the screens.
        with open(pkl_file2, 'rb') as fd:
            atm2 = pickle.load(fd)

        # And *now* we can unpickle pkl_file again
        with open(pkl_file, 'rb') as fd:
            atm = pickle.load(fd)
        assert atm == atm2
        wf3 = atm.wavefront(xs, ys, ts)
        np.testing.assert_equal(wf, wf3)


@timer
def test_user_screen():
    # Mimic an OpticalScreen using a UserScreen.
    rng = galsim.UniformDeviate(57721)
    for _ in range(10):
        aberrations = np.empty(7)
        rng.generate(aberrations)
        aberrations -= 0.5
        aberrations *= 0.1
        aberrations[0:2] = 0.0
        Zscreen = galsim.OpticalScreen(
            diam=4.0,
            aberrations=aberrations,
            lam_0=750.0
        )

        u1 = np.linspace(-2, 2, 200)
        u, v = np.meshgrid(u1, u1)
        wf = Zscreen.wavefront(u, v)

        table = galsim.LookupTable2D(u1, u1, wf, interpolant='spline')
        uscreen = galsim.UserScreen(table)

        rr = np.empty(1000)
        th = np.empty(1000)
        rng.generate(rr)
        rng.generate(th)
        rr = np.sqrt(rr)
        rr *= 1.95  # Stay a bit away from the edges
        th *= 2*np.pi
        uu = rr*np.cos(th)
        vv = rr*np.sin(th)

        wf = Zscreen.wavefront(uu, vv)
        twf = uscreen.wavefront(uu, vv)
        np.testing.assert_allclose(wf, twf, rtol=1e-12, atol=1e-12)

        dwfdx, dwfdy = Zscreen.wavefront_gradient(uu, vv)
        dtwfdx, dtwfdy = uscreen.wavefront_gradient(uu, vv)

        np.testing.assert_allclose(dwfdx, dtwfdx, rtol=1e-11, atol=1e-11)
        np.testing.assert_allclose(dwfdy, dtwfdy, rtol=1e-11, atol=1e-11)

        # PSFs should be nearly identical
        Zpsf = galsim.PhaseScreenPSF(Zscreen, lam=750, diam=4.0)
        tpsf = galsim.PhaseScreenPSF(uscreen, lam=750, diam=4.0)
        Zimg = Zpsf.drawImage(scale=0.01, nx=100, ny=100)
        timg = tpsf.drawImage(scale=0.01, nx=100, ny=100)
        np.testing.assert_allclose(Zimg.array, timg.array, rtol=0, atol=1e-10)
        print(np.max(Zimg.array))

    check_pickle(
        uscreen,
        lambda sc:
            (
                sc,
                galsim.PhaseScreenPSF(sc, 750.0, diam=4.0).drawImage(),
                galsim.PhaseScreenPSF(sc, 750.0, diam=4.0).drawImage(
                    method='phot', rng=rng.duplicate(), n_photons=100
                ),
                galsim.PhaseScreenPSF(sc, 750.0, diam=4.0, geometric_shooting=False).drawImage(
                    method='phot', rng=rng.duplicate(), n_photons=100
                ),
            )
    )
    uscreen2 = galsim.UserScreen(table, diam=2)
    uscreen3 = galsim.UserScreen(table, diam=2, obscuration=0.5)
    check_pickle(uscreen2)
    check_pickle(uscreen3)
    check_all_diff([uscreen, uscreen2, uscreen3])


@timer
def test_uv_persistence(run_slow):
    from scipy.spatial.distance import cdist
    if run_slow:
        nphot = 1000000
    else:
        nphot = 1000

    # Check that reasonable pupil samples are used and persisted when phase screen shooting.
    u = galsim.UniformDeviate(5185)
    for _ in range(3):
        diam = u()+1
        obscuration = u()*0.5
        nstruts = int(u()*4)
        strut_thick = u()*0.01
        strut_angle = u()*2*np.pi*galsim.radians
        aper = galsim.Aperture(
            diam=diam, obscuration=obscuration, nstruts=nstruts, strut_thick=strut_thick,
            strut_angle=strut_angle, pupil_plane_scale=diam/20
        )
        with assert_warns(galsim.GalSimWarning):
            # Warning: Input pupil_plane_scale may be too large for good sampling.
            illuminated = np.vstack([aper.u_illuminated, aper.v_illuminated]).T

        psf = galsim.OpticalPSF(lam=500, diam=diam, aper=aper, geometric_shooting=True)
        photons = psf.drawImage(save_photons=True, method='phot', n_photons=nphot).photons
        pupil = np.vstack([photons.pupil_u, photons.pupil_v]).T

        mindist = np.min(cdist(illuminated, pupil), axis=0)
        uscale = aper.u[0,1] - aper.u[0,0]
        vscale = aper.v[1,0] - aper.v[0,0]
        assert np.max(mindist) < np.hypot(uscale, vscale)*0.5

        check_pickle(photons)


@timer
def test_t_persistence():
    rng = galsim.BaseDeviate(10)
    atm = galsim.Atmosphere(screen_size=10.0, altitude=[0,1,2,3], r0_500=0.2, rng=rng)
    psf = atm.makePSF(t0=10.0, lam=500.0, diam=1.0, exptime=15.0, time_step=0.025)
    nphot = 1_000_000
    photons = psf.drawImage(save_photons=True, method='phot', n_photons=nphot).photons
    assert photons.hasAllocatedTimes()
    assert np.min(photons.time) > 10.0
    assert np.max(photons.time) < 25.0


@timer
def test_convolve_phasepsf():
    # This snippet didn't use to be allowed, since the two psfs populate different
    # pupil angles.
    star = galsim.DeltaFunction(flux=10)
    psf1 = galsim.Atmosphere(screen_size=10).makePSF(lam=700, diam=8)
    psf2 = galsim.OpticalPSF(lam=700, diam=8, geometric_shooting=True)
    sed = galsim.SED('vega.txt', wave_type='nm', flux_type='fphotons')
    obj = galsim.Convolve(star * sed, psf1, psf2)
    bandpass = galsim.Bandpass('LSST_r.dat', wave_type='nm')
    obj = obj.withFlux(10, bandpass)
    rng = galsim.BaseDeviate(1234)
    im = obj.drawImage(bandpass, method='phot', n_photons=10, rng=rng)

    # The main thing is that it works.  But check that flux makes sense.
    assert im.array.sum() == 10


if __name__ == "__main__":
    runtests(__file__)
