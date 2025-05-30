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

import numpy as np
import os
import sys

import galsim
from galsim_test_helpers import *


@timer
def test_vk(run_slow):
    """Test the generation of VonKarman profiles
    """
    if run_slow:
        lams = [300.0, 500.0, 1100.0]
        r0_500s = [0.05, 0.15, 0.3]
        L0s = [1e10, 25.0, 10.0]
        do_deltas = [False, True]
    else:
        lams = [500.0]
        r0_500s = [0.2]
        L0s = [25.0]
        do_deltas = [False]
    for lam in lams:
        for r0_500 in r0_500s:
            r0 = r0_500*(lam/500)**(6./5)
            for L0 in L0s:
                for do_delta in do_deltas:
                    kwargs = {'lam':lam, 'r0':r0, 'L0':L0, 'do_delta':do_delta}
                    print(kwargs)
                    delta_amp = np.exp(-0.5*0.172629*(r0/L0)**(-5./3.))
                    if delta_amp > 1.e-3:
                        print("Skip this combination, since delta > maxk_threshold")
                        continue

                    vk = galsim.VonKarman(flux=2.2, **kwargs)
                    np.testing.assert_almost_equal(vk.flux, 2.2)

                    gsp = galsim.GSParams(xvalue_accuracy=1.e-8, kvalue_accuracy=1.e-8)
                    vk2 = galsim.VonKarman(flux=2.2, gsparams=gsp, **kwargs)
                    assert vk2 != vk
                    assert vk2 == vk.withGSParams(gsp)
                    assert vk2 == vk.withGSParams(xvalue_accuracy=1.e-8, kvalue_accuracy=1.e-8)

                    check_basic(vk, "VonKarman")
                    check_pickle(vk)

                    img = galsim.Image(16, 16, scale=0.25)
                    if not do_delta:
                        do_shoot(vk, img, "VonKarman")
                        do_kvalue(vk, img, "VonKarman")

    with np.testing.assert_raises(galsim.GalSimIncompatibleValuesError):
        vk = galsim.VonKarman(lam=500, r0=0.1, r0_500=0.2)
    with np.testing.assert_raises(galsim.GalSimIncompatibleValuesError):
        vk = galsim.VonKarman(lam=500)


@timer
def test_vk_delta():
    """Test a VonKarman with a significant delta-function amplitude"""
    kwargs = {'lam':1100.0, 'r0':0.8, 'L0':5.0, 'flux':2.2}
    # Try to see if we can catch the warning first
    with assert_warns(galsim.GalSimWarning):
        vk = galsim.VonKarman(**kwargs)

    kwargs['suppress_warning'] = True
    vk = galsim.VonKarman(**kwargs)
    check_pickle(vk)

    # This profile has more than 15% of its flux in the delta-function component.
    assert vk.delta_amplitude > 0.15 * vk.flux
    # If do_delta is False (the default), then the asymptotic kValue should still be zero.
    np.testing.assert_almost_equal(vk.kValue(1e10, 0).real, 0.0)
    # But if we use do_delta=True, then the asymptotic kValue should be that of the delta function.
    vkd = galsim.VonKarman(do_delta=True, **kwargs)
    check_pickle(vkd)
    np.testing.assert_almost_equal(vkd.kValue(1e10, 0).real, vkd.delta_amplitude)

    # Either way, the fluxes should be the same.
    np.testing.assert_almost_equal(vk.flux, vkd.flux)
    assert vk != vkd
    # The half-light-radius of the profile with do_delta=True should be smaller though, as we're
    # accounting for the 15% flux at r=0 in this case
    assert vkd.half_light_radius < vk.half_light_radius


@timer
def test_vk_scale():
    """Test vk scale argument"""
    kwargs = {'lam':500, 'r0':0.2, 'L0':25.0, 'flux':2.2}
    vk_arcsec = galsim.VonKarman(scale_unit=galsim.arcsec, **kwargs)
    vk_arcmin = galsim.VonKarman(scale_unit='arcmin', **kwargs)
    check_pickle(vk_arcmin)

    np.testing.assert_almost_equal(vk_arcsec.flux, vk_arcmin.flux)
    np.testing.assert_almost_equal(vk_arcsec.kValue(0.0, 0.0), vk_arcmin.kValue(0.0, 0.0))
    np.testing.assert_almost_equal(vk_arcsec.kValue(0.0, 10.0), vk_arcmin.kValue(0.0, 600.0))
    np.testing.assert_almost_equal(vk_arcsec.xValue(0.0, 6.0), vk_arcmin.xValue(0.0, 0.1))

    img1 = vk_arcsec.drawImage(nx=32, ny=32, scale=0.2)
    img2 = vk_arcmin.drawImage(nx=32, ny=32, scale=0.2/60.0)
    np.testing.assert_almost_equal(img1.array, img2.array)


@timer
def test_vk_properties():
    """Test some basic properties of the VonKarman profile.
    """
    # Regression test based on v2.3.5 version of the code.

    test_flux = 1.8
    psf = galsim.VonKarman(lam=500, r0=0.2, L0=25.0, flux=test_flux)

    # Check various properties
    np.testing.assert_equal(psf.centroid, galsim.PositionD(0,0))
    np.testing.assert_almost_equal(psf.maxk, 24.511275061996837)
    np.testing.assert_almost_equal(psf.stepk, 1.1025979141287368, decimal=6)
    np.testing.assert_almost_equal(psf.kValue(0,0), test_flux+0j)
    np.testing.assert_almost_equal(psf.xValue(0,0), 7.91805413536067)
    np.testing.assert_almost_equal(psf.kValue(0,0), (1+0j) * test_flux)
    np.testing.assert_almost_equal(psf.flux, test_flux)
    np.testing.assert_almost_equal(psf.xValue(0,0), psf.max_sb)

    # Check input flux vs output flux
    for inFlux in np.logspace(-2, 2, 10):
        psfFlux = galsim.VonKarman(lam=500, r0=0.2, L0=25.0, flux=inFlux)
        outFlux = psfFlux.flux
        np.testing.assert_almost_equal(outFlux, inFlux)

    # Check that stepk and maxk scale correctly with r0,L0
    psf2 = galsim.VonKarman(lam=500, r0=0.2/5, L0=25.0/5, flux=test_flux)
    np.testing.assert_almost_equal(psf2.maxk, psf.maxk/5)
    # This is not exact, since it's a computed quantity from the lookup table, so only
    # equal to about 1%.
    np.testing.assert_allclose(psf2.stepk, psf.stepk/5, rtol=0.01)

    # Equivalent if scale lam instead.
    psf2 = galsim.VonKarman(lam=5*500, r0=0.2, L0=25.0, flux=test_flux)
    np.testing.assert_almost_equal(psf2.maxk, psf.maxk/5)
    np.testing.assert_allclose(psf2.stepk, psf.stepk/5, rtol=0.01)


@timer
def test_vk_shoot():
    """Test VonKarman with photon shooting.  Particularly the flux of the final image.
    """
    rng = galsim.BaseDeviate(1234)
    obj = galsim.VonKarman(lam=500, r0=0.2, flux=1.e4)
    im = galsim.Image(100,100, scale=1)
    im.setCenter(0,0)
    added_flux, photons = obj.drawPhot(im, poisson_flux=False, rng=rng.duplicate())
    print('obj.flux = ',obj.flux)
    print('added_flux = ',added_flux)
    print('photon fluxes = ',photons.flux.min(),'..',photons.flux.max())
    print('image flux = ',im.array.sum())
    assert np.isclose(added_flux, obj.flux)
    assert np.isclose(im.array.sum(), obj.flux)
    photons2 = obj.makePhot(poisson_flux=False, rng=rng)
    assert photons2 == photons, "VonKarman makePhot not equivalent to drawPhot"

    obj = galsim.VonKarman(lam=500, r0=0.2, L0=10., flux=1.e4)
    added_flux, photons = obj.drawPhot(im, poisson_flux=False, rng=rng.duplicate())
    print('obj.flux = ',obj.flux)
    print('added_flux = ',added_flux)
    print('photon fluxes = ',photons.flux.min(),'..',photons.flux.max())
    print('image flux = ',im.array.sum())
    assert np.isclose(added_flux, obj.flux)
    assert np.isclose(im.array.sum(), obj.flux)
    photons2 = obj.makePhot(poisson_flux=False, rng=rng)
    assert photons2 == photons, "VonKarman makePhot not equivalent to drawPhot"

    obj = galsim.VonKarman(lam=700, r0=0.02, L0=10., flux=1.e4)
    im = galsim.Image(500,500, scale=1)
    im.setCenter(0,0)
    added_flux, photons = obj.drawPhot(im, poisson_flux=False, rng=rng.duplicate())
    print('obj.flux = ',obj.flux)
    print('added_flux = ',added_flux)
    print('photon fluxes = ',photons.flux.min(),'..',photons.flux.max())
    print('image flux = ',im.array.sum())
    assert np.isclose(added_flux, obj.flux)
    assert np.isclose(im.array.sum(), obj.flux)
    photons2 = obj.makePhot(poisson_flux=False, rng=rng.duplicate())
    assert photons2 == photons, "VonKarman makePhot not equivalent to drawPhot"

    # Can treat the profile as a convolution of a delta function and put it in a photon_ops list.
    delta = galsim.DeltaFunction(flux=1.e4)
    psf = galsim.VonKarman(lam=700, r0=0.02, L0=10.)
    photons3 = delta.makePhot(poisson_flux=False, rng=rng.duplicate(), photon_ops=[psf])
    assert photons3 == photons, "Using VonKarman in photon_ops not equivalent to drawPhot"


@timer
def test_vk_ne():
    gsp = galsim.GSParams(maxk_threshold=1.1e-3, folding_threshold=5.1e-3)

    objs = [galsim.VonKarman(lam=500.0, r0=0.2),
            galsim.VonKarman(lam=500.0, r0=0.2, L0=20.0),
            galsim.VonKarman(lam=500.0, r0=0.2, L0=20.0, flux=2.2),
            galsim.VonKarman(lam=500.0, r0=0.2, L0=1e11),
            galsim.VonKarman(lam=550.0, r0=0.1, L0=20.0),
            galsim.VonKarman(lam=550.0, r0=0.1, L0=20.0, do_delta=True),
            galsim.VonKarman(lam=550.0, r0=0.1, L0=20.0, scale_unit=galsim.arcmin),
            galsim.VonKarman(lam=550.0, r0=0.1, L0=20.0, gsparams=gsp),
            galsim.VonKarman(lam=550.0, r0=0.1, L0=20.0, gsparams=gsp, force_stepk=1.0)]
    check_all_diff(objs)


@timer
def test_vk_eq_kolm():
    lam = 500.0
    r0 = 0.2
    L0 = 1e10  # Need to make this surprisingly large to make vk -> kolm.
    flux = 3.3
    kolm = galsim.Kolmogorov(lam=lam, r0=r0, flux=flux)
    vk = galsim.VonKarman(lam=lam, r0=r0, L0=L0, flux=flux)

    np.testing.assert_allclose(kolm.xValue(0,0), vk.xValue(0,0), rtol=5e-4, atol=0)

    kolm_img = kolm.drawImage(nx=24, ny=24, scale=0.2)
    vk_img = vk.drawImage(nx=24, ny=24, scale=0.2)
    np.testing.assert_allclose(kolm_img.array, vk_img.array, atol=flux*4e-5, rtol=0)


@timer
def test_vk_fitting_formulae():
    #         lam, r0_500, L0
    params = [(650, 0.15, 10.0),
              (450, 0.12, 25.0),
              (900, 0.18, 100.0)]

    def predicted_FWHM_ratio(r0, L0):
        """Fitting formula for VonKarman FWHM / Kolmogorov FWHM
        from Martinez++2014
        """
        return np.sqrt(1 - 2.183*(r0/L0)**0.356)

    def predicted_HLR_ratio(r0, L0):
        """Fitting formula for VonKarman HLR / Kolmogorov HLR
        from Martinez++2014
        """
        return np.sqrt(1 - 1.534*(r0/L0)**0.347)

    for lam, r0_500, L0 in params:
        print(lam, r0_500, L0)
        r0 = r0_500*(lam/500.0)**(6./5)
        kolm = galsim.Kolmogorov(lam=lam, r0=r0)
        vk = galsim.VonKarman(lam=lam, r0=r0, L0=L0)
        vk2 = galsim.VonKarman(lam=lam, r0_500=r0_500, L0=L0)
        np.testing.assert_allclose(vk.r0, vk2.r0)
        np.testing.assert_allclose(vk.r0_500, vk2.r0_500)
        for prof in [vk, vk2]:
            HLR_ratio = prof.calculateHLR() / kolm.calculateHLR()
            FWHM_ratio = prof.calculateFWHM() / kolm.calculateFWHM()
            print(HLR_ratio)
            print(FWHM_ratio)
            np.testing.assert_allclose(HLR_ratio, predicted_HLR_ratio(r0, L0), rtol=0.015)
            np.testing.assert_allclose(FWHM_ratio, predicted_FWHM_ratio(r0, L0), rtol=0.015)


@timer
def test_vk_gsp():
    """Test that we can construct a vK with non-standard folding_threshold.
    """
    # default folding_threshold is 5e-3.
    # We can't go too much smaller than this for such a flat asymptotic profile, but check a little
    # bit further works.
    gsp1 = galsim.GSParams(folding_threshold=1e-2)
    gsp2 = galsim.GSParams(folding_threshold=2e-3)

    # Just testing that these construct successfully
    galsim.VonKarman(lam=700, r0=0.1, L0=24.3, gsparams=gsp1)
    galsim.VonKarman(lam=700, r0=0.1, L0=24.3, gsparams=gsp2)


def vk_benchmark():
    import time
    t0 = time.time()
    vk = galsim.VonKarman(lam=700, r0=0.1, L0=24.3)
    vk.drawImage(nx=16, ny=16, scale=0.2)
    t1 = time.time()
    print("Time to create/draw first time: {:6.3f}s".format(t1-t0))  # ~0.7s
    for i in range(10):
        vk.drawImage(nx=16, ny=16, scale=0.2)
    t2 = time.time()
    print("Time to draw 10 more: {:6.3f}s".format(t2-t1))  # ~0.07s
    for i in range(100):
        vk.drawImage(nx=16, ny=16, scale=0.2, method='phot', n_photons=50000)
    t3 = time.time()
    print("Time to photon-shoot 100 more with 50000 photons each: {:6.3f}s".format(t3-t2))  # ~0.9s


@timer
def test_vk_r0(run_slow):
    """Test a special r0 value that resulted in an error, reported in issue #957.

    Note: the resolution of the bug was to add explicit split points for the first several
    j0 zeros.  Without that, the integral in rawXValue can spuriously fail badly, leading to
    an invalid estimate of the total integrated flux within R=pi/stepk.

    Update: With the new Ogata method for doing the Hankel transform, this seems no longer to
    be necessary.  However, we continue to test these r values anyway.
    """
    # The first one was issue #957.
    # Aaron Roodman ran across another, which is now included here as well.
    r0_list = [0.146068884, 0.16879518207956518]

    for r0 in r0_list:
        vk = galsim.VonKarman(L0=25.,lam=700.,r0=r0)
        check_basic(vk, "VonKarman, r0=%s"%r0)

    if run_slow:
        # Josh then tried a bunch more random triples of r0_500, lam, L0 to find more failures,
        # which are given in input/vk_fail.txt.
        r0_500_list, lam_list, L0_list = np.loadtxt('input/vk_fail.txt').T
        for r0_500, lam, L0 in zip(r0_500_list, lam_list, L0_list):
            print(r0_500,lam,L0)
            vk = galsim.VonKarman(L0=L0,lam=lam,r0_500=r0_500)
            #check_basic(vk, "VonKarman, r0_500=%s"%r0_500)


@timer
def test_vk_force_stepk():
    """Check that manually forcing stepk works"""
    vk1 = galsim.VonKarman(r0_500=0.1, L0=25.0, lam=750.0)
    vk2 = galsim.VonKarman(r0_500=0.1, L0=25.0, lam=750.0, force_stepk=10.0)

    # Make sure we get expected stepk
    assert vk1.stepk != vk2.stepk
    assert vk2.stepk == 10.0

    # Many products will actually be the same for both
    # Asking for the half_light_radius or xValue will trigger the table build,
    # which is identical for each.
    assert vk1.half_light_radius == vk2.half_light_radius
    assert vk1.xValue(0, 1) == vk2.xValue(0, 1)

    # Images will be the same if you assert specific bounds
    img1 = vk1.drawImage(nx=50, ny=50, scale=0.2, method='fft')
    img2 = vk2.drawImage(nx=50, ny=50, scale=0.2, method='fft')

    np.testing.assert_equal(img1.array, img2.array)

    # Though "goodImageSize" will differ.
    assert vk1.getGoodImageSize(0.2) != vk2.getGoodImageSize(0.2)

    # Can we pickle?
    check_pickle(vk2)
    check_pickle(vk2, lambda obj:obj.stepk)
    check_basic(vk2, 'vk2', do_x=False)  # x fails b/c stamp size is bad

    img = galsim.Image(50, 50, scale=0.2)
    do_shoot(vk2, img, "VonKarman")

    # Check works with scale
    vk3 = galsim.VonKarman(
        r0_500=0.1, L0=25.0, lam=750.0, force_stepk=10.0,
        scale_unit=galsim.radians
    )
    assert vk3.stepk == 10.0
    assert vk3.scale_unit == galsim.radians

    # force_stepk is retained through a reflux
    vk4 = vk3.withFlux(11.0)
    assert vk4.flux == 11.0
    assert vk3.force_stepk == vk4.force_stepk

@timer
def test_low_folding_threshold():
    """Test VonKarman with a very low folding_threshold.
    """
    folding_threshold = 1e-4
    pixel_scale = 0.2
    kwargs = {'lam':500, 'r0':0.2, 'L0':25.0, 'flux':2.2}
    gsparams = galsim.GSParams(folding_threshold=folding_threshold)
    psf = galsim.VonKarman(gsparams=gsparams, **kwargs)
    image_size = psf.getGoodImageSize(pixel_scale)
    print('ft = 1.e-4: psf.getGoodImageSize:', image_size)
    assert image_size == 298

    folding_threshold = 1e-6
    gsparams = galsim.GSParams(folding_threshold=folding_threshold)
    psf = galsim.VonKarman(gsparams=gsparams, **kwargs)
    image_size = psf.getGoodImageSize(pixel_scale)
    print('ft = 1.e-6: psf.getGoodImageSize:', image_size)
    assert image_size == 600

    # Check an extremely small L0
    kwargs['L0'] = 1.0
    with assert_warns(galsim.GalSimWarning):
        # This low an L0 has a non-negligible delta function, hence a warning.
        psf = galsim.VonKarman(gsparams=gsparams, **kwargs)
    image_size = psf.getGoodImageSize(pixel_scale)
    print('L0=1.0, ft = 1.e-6: psf.getGoodImageSize:', image_size)
    assert image_size == 600


if __name__ == "__main__":
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--benchmark", action='store_true', help="Run timing benchmark")

    runtests(__file__, parser=parser)

    args, unknown_args = parser.parse_known_args()
    if args.benchmark:
        vk_benchmark()
