import numpy as np
import camb
import git
from scipy.optimize import fsolve
from .flatsky import make_gaussian_realisation, get_lpf_hpf
from .tools import get_bl, get_nl
from .inpaint import get_covariance, inpainting

# Constants
c = 299792458.0  # Speed of light - [c] = m/s
h_p = 6.626068e-34  # Planck's constant in SI units
k_b = 1.38065e-23  # Boltzmann constant in SI units
TCMB = 2.725  # Canonical CMB in Kelvin


def d_b(dt, frequency):
    """
    Blackbody function.
    :param dt: Differential temperature
    :param frequency: Frequency space
    :return: Spectral brightness distribution
    """

    dt = np.asanyarray(dt)
    frequency = np.asanyarray(frequency)

    temp = TCMB / (1 + dt)
    x = (h_p / (k_b * temp)) * frequency
    I = ((2 * h_p) / (c ** 2)) * (k_b * temp / h_p) ** 3
    return I * (x ** 4 * np.exp(x) / ((np.exp(x) - 1) ** 2)) / temp * dt


def classical_tsz(y, frequency):
    """
    Calculate the classical tSZ function.
    :param y: Galaxy cluster y-value
    :param frequency: Frequency space
    :return: Spectral brightness distribution
    """

    y = np.asanyarray(y)
    frequency = np.asanyarray(frequency)

    x_b = (h_p / (k_b * TCMB)) * frequency
    bv = 2 * k_b * TCMB * ((frequency ** 2) / (c ** 2)) * (x_b / (np.exp(x_b) - 1))
    return y * ((x_b * np.exp(x_b)) / (np.exp(x_b) - 1)) * (x_b * ((np.exp(x_b) + 1) / (np.exp(x_b) - 1)) - 4) * bv


class Parameters:
    """
    A parameter class that encapsulates creation of auxiliary parameters.
    """

    def create_cmb_map(self, angular_resolution, realizations, seed=40):
        """
        Creates a map of the CMB anisotropies using CAMB.
        :return: a cmb map in Kelvin
        """

        # Set a seed
        np.random.seed(seed)

        # Set up a new set of parameters for CAMB
        pars = camb.CAMBparams()

        # This function sets up with one massive neutrino and helium set using BBN consistency
        pars.set_cosmology(H0=67.5, ombh2=0.022, omch2=0.122, mnu=0.06, omk=0, tau=0.06)
        pars.InitPower.set_params(As=2e-9, ns=0.965, r=0)
        lmax = 10000
        pars.set_for_lmax(lmax, lens_potential_accuracy=0)

        # calculate results for these parameters
        results = camb.get_results(pars)

        # get dictionary of CAMB power spectra
        powers = results.get_cmb_power_spectra(pars, CMB_unit='K')
        totCL = powers['total']

        el = np.arange(totCL.shape[0])
        dl_tt = totCL[:, 0]
        dl_tt[0] = 0
        dl_fac = el * (el + 1) / 2 / np.pi
        cl_tt = (TCMB ** 2. * dl_tt * 1e12) / dl_fac
        cl_dic = {'TT': cl_tt}

        # params or supply a params file
        dx = angular_resolution
        boxsize_am = 200.  # boxsize in arcmins
        nx = int(boxsize_am / dx)
        mapparams = [nx, nx, dx, dx]
        x1, x2 = -nx / 2. * dx, nx / 2. * dx

        # beam and noise levels
        noiseval = 1.0  # uK-arcmin
        beamval = angular_resolution  # arcmins
        bl = get_bl(beamval, el, make_2d=1, mapparams=mapparams)

        # for inpainting
        noofsims = 1000
        mask_radius_inner = 8  # arcmins
        mask_radius_outer = 60  # arcmins

        # get ra, dec or map-pixel grid
        ra = np.linspace(x1, x2, nx)  # arcmins
        dec = np.linspace(x1, x2, nx)  # arcmins
        ra_grid, dec_grid = np.meshgrid(ra, dec)

        # get beam and noise
        nl_dic = {}
        nl = [get_nl(noiseval, el)]
        nl_dic['T'] = nl[0]
        lpf = get_lpf_hpf(mapparams, 3000, filter_type=0)

        cmb_map = np.asarray([make_gaussian_realisation(mapparams, el, cl_tt, bl=bl)])
        noise_map = np.asarray([make_gaussian_realisation(mapparams, el, nl[0])])
        sim_map = cmb_map + noise_map

        sigma_dic = get_covariance(ra_grid=ra_grid, dec_grid=dec_grid, mapparams=mapparams, el=el,
                                   cl_dic=cl_dic, bl=bl, lpf=lpf, nl_dic=nl_dic, noofsims=noofsims,
                                   mask_radius_inner=mask_radius_inner, mask_radius_outer=mask_radius_outer,
                                   low_pass_cutoff=1)

        cmb_anis = []
        for i in range(realizations):
            # perform inpainting
            sim_map_dic = {'T': sim_map}
            (cmb_inpainted_map, sim_map_inpainted,
             sim_map_filtered) = inpainting(map_dic_to_inpaint=sim_map_dic,
                                            ra_grid=ra_grid,
                                            dec_grid=dec_grid,
                                            mapparams=mapparams, el=el,
                                            cl_dic=cl_dic, bl=bl, lpf=lpf,
                                            nl_dic=nl_dic,
                                            mask_radius_inner=mask_radius_inner,
                                            mask_radius_outer=mask_radius_outer,
                                            low_pass_cutoff=1,
                                            sigma_dic=sigma_dic)
            cmb_anis.append(sim_map_filtered[33:34, 33:34] - sim_map_inpainted[33:34, 33:34])

        cmb_anis = np.asarray(cmb_anis).flatten()*1e-6

        return cmb_anis

    def create_ksz_map(self, angular_resolution, seed=40):
        """
        Creates a map of the CMB anisotropies using CAMB.
        :return: a cmb map in Kelvin
        """

        # Set a seed
        np.random.seed(seed)

        el = np.arange(5051)
        dl_tt = np.asanyarray([3e-12] * 5051)
        dl_tt[0] = 0
        dl_fac = el * (el + 1) / 2 / np.pi
        cl_tt = (TCMB ** 2. * dl_tt * 1e12) / (dl_fac)

        # params or supply a params file
        dx = angular_resolution
        boxsize_am = 3000.  # boxsize in arcmins
        nx = int(boxsize_am / dx)
        mapparams = [nx, nx, dx, dx]

        beamval = angular_resolution  # arcmins
        bl = get_bl(beamval, el, make_2d=1, mapparams=mapparams)

        KSZ_map = np.asarray([make_gaussian_realisation(mapparams, el, cl_tt, bl=bl)])
        KSZ_T = KSZ_map.reshape(nx, nx) * 1e-6  # Convert to K

        return KSZ_T

    def create_tsz_map(self, angular_resolution, seed=40):
        """
        Creates a map of the CMB anisotropies using CAMB.
        :return: a cmb map in Kelvin
        """

        # Set a seed
        np.random.seed(seed)

        # Flat power spectrum
        frequency = 143e9

        dl_tt = np.asanyarray([3.42e-12] * 5051)
        dl_tt[0] = 0
        el = np.arange(5051)
        dl_fac = el * (el + 1) / 2 / np.pi
        cl_tt = (TCMB ** 2. * dl_tt * 1e12) / (dl_fac)

        # params or supply a params file
        dx = angular_resolution
        boxsize_am = 3000.  # boxsize in arcmins
        nx = int(boxsize_am / dx)
        mapparams = [nx, nx, dx, dx]

        beamval = angular_resolution  # arcmins
        bl = get_bl(beamval, el, make_2d=1, mapparams=mapparams)

        TSZ_map = np.asarray([make_gaussian_realisation(mapparams, el, cl_tt, bl=bl)])
        TSZ_T = TSZ_map.reshape(nx, nx) * 1e-6  # Convert to K
        TSZ_Y = np.copy(TSZ_T)

        def func(y_value, dt):
            return classical_tsz(y=y_value, frequency=frequency) - d_b(dt=dt, frequency=frequency)

        for i in range(nx):
            for k in range(nx):
                TSZ_Y[i][k] = fsolve(func, np.asanyarray([0]), args=[TSZ_T[i][k]])

        return TSZ_Y

    def create_parameter_file(self, angular_resolution=3.0, realizations=100):
        """
        Creates a file of fiducial parameters for contaminants including CMB, CIB, and secondary tsz and ksz.
        :param angular_resolution:
        :param realizations: amount of realizations
        :return None:
        """

        params = [[0, 0, 0, 0, 0]]
        params = np.asarray(params)

        # Get CMB anisotropies
        amp_cmb = self.create_cmb_map(angular_resolution=angular_resolution, realizations=realizations)

        # Create secondary kSZ, tSZ map
        ksz_map = self.create_ksz_map(angular_resolution=angular_resolution)
        tsz_map = self.create_tsz_map(angular_resolution=angular_resolution)

        # Make realizations
        for i in range(realizations):
            # Pick coordinates of SIDES continuum
            # Low and high defined by shape of SIDES catalog given
            sides_long = np.random.randint(low=0, high=160)
            sides_lat = np.random.randint(low=0, high=160)

            # Pick coordinates of random map
            # Low and high defined from CMB map size
            long = np.random.randint(low=2, high=998)
            lat = np.random.randint(low=2, high=998)

            # Make CMB secondary anisotropies
            amp_ksz = ksz_map[long, lat]
            amp_ksz = amp_ksz - np.mean(ksz_map[long - 2:long + 3, lat - 2:lat + 3])

            amp_tsz = tsz_map[long, lat]
            amp_tsz = amp_tsz - np.mean(tsz_map[long - 2:long + 3, lat - 2:lat + 3])

            params_realization = [[sides_long, sides_lat, amp_cmb[i], amp_ksz, amp_tsz]]
            params = np.append(arr=params, values=params_realization, axis=0)

        params = params[1:, :]

        repo = git.Repo('.', search_parent_directories=True)

        # Write simulation output, change directory/name
        np.save(repo.working_tree_dir + '/files/parameter_file_' + str(realizations), arr=params, allow_pickle=True)
