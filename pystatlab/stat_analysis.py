import numpy as np
import scipy.stats as st
from tqdm import tqdm

def correlation_ratio(values, categories):
    """
    Calculates the correlation ratio, a measure of the relationship between a categorical variable and a continuous variable.

    The correlation ratio (η) measures the extent to which a continuous variable changes within categories defined by a 
    categorical variable. It's a way to quantify the association between a categorical independent variable and a continuous 
    dependent variable.

    Parameters
    ----------
    values : array-like
        An array of continuous data values (dependent variable).
    categories : array-like
        An array of categories corresponding to the values (independent variable).

    Returns
    -------
    float
        The calculated correlation ratio, a value between 0 and 1, where 0 indicates no association and 1 indicates a perfect association.

    Notes
    -----
    The formula for the correlation ratio involves dividing the sum of squares between groups (SSB) by the total sum of squares (SSB + SSW), 
    where SSW is the sum of squares within groups. A higher value indicates a stronger relationship between the categorical and continuous variables.

    Reference
    ---------
    More information about the correlation ratio can be found on Wikipedia: https://en.wikipedia.org/wiki/Correlation_ratio
    """
    
    values = np.array(values)
    categories = np.array(categories)
    
    ssw = 0 
    ssb = 0 
    for category in set(categories):
        subgroup = values[np.where(categories == category)[0]]
        ssw += sum((subgroup-np.mean(subgroup))**2)
        ssb += len(subgroup)*(np.mean(subgroup)-np.mean(values))**2

    return (ssb / (ssb + ssw))**.5


def cramers_v(rc_table, observations='raise'):
    
    """
    Calculates Cramér's V statistic, a measure of association between two categorical variables.

    Cramér's V is based on a nominal variation of the chi-squared test, and it provides a measure of the strength 
    of association between two categorical variables with values ranging from 0 (no association) to 1 (complete association).

    Parameters
    ----------
    rc_table : array-like
        A two-dimensional array (contingency table) representing the frequencies or counts of the categorical variables.
    observations : str, optional
        Handling method for small sample sizes: 'raise' to raise an error if any expected frequency is less than 5, 
        'ignore' to compute the statistic without raising an error (default is 'raise').

    Returns
    -------
    dict
        A dictionary containing 'correlation' (Cramér's V value), 'pvalue' (p-value of the chi-squared test), 
        and 'chi2' (chi-squared statistic).

    Notes
    -----
    The function optionally applies Yates' correction for continuity in case of small sample sizes. 
    Cramér's V is an appropriate measure for nominal (categorical) data and is symmetric; it does not depend 
    on the order of variables.

    Reference
    ---------
    More information about Cramér's V can be found on Wikipedia: https://en.wikipedia.org/wiki/Cram%C3%A9r%27s_V
    """
    
    rc_table = np.array(rc_table)
    
    def get_corr(rc_table):
        
        if rc_table.min() < 10:
            correction = True
        else:
            correction = False
            
        n = rc_table.sum()
        chi2_stats = st.chi2_contingency(rc_table, correction=correction)
        cramers_v = (chi2_stats[0]/(n*min(rc_table.shape[0]-1, rc_table.shape[1]-1)))**.5        
        return {'correlation':cramers_v, 'pvalue': chi2_stats[1], 'chi2': chi2_stats[0]}
    
    if observations == 'raise':
        if rc_table.min() < 5:
            raise ValueError('Not enough observations')
        else:
            return get_corr(rc_table)
    elif observations == 'ignore':
        return get_corr(rc_table)
    
def robust_mean(data, trunc_level=.2, type_='truncated'):
    """
    Calculates a robust mean of the data using either the truncated mean or Winsorized mean method.

    This function aims to provide a mean value that is less sensitive to outliers or extreme values by either
    truncating or Winsorizing the data based on a specified truncation level.

    Parameters
    ----------
    data : array-like
        The data from which the robust mean is to be calculated.
    trunc_level : float, optional
        The level at which data should be truncated or Winsorized, given as a proportion (default is 0.2).
    type_ : str, optional
        The type of robust mean to calculate: 'truncated' for truncated mean and 'winsorized' for Winsorized mean 
        (default is 'truncated').

    Returns
    -------
    float
        The calculated robust mean of the data.

    References
    ----------
    More information about the truncated mean can be found at: https://en.wikipedia.org/wiki/Truncated_mean
    More information about the Winsorized mean can be found at: https://en.wikipedia.org/wiki/Winsorized_mean
    """
    data = np.array(data)
    q = np.quantile(data, q=[trunc_level / 2, 1 - trunc_level / 2])
    trunc_data = data[(data > q[0]) & (data < q[1])]
    if type_ == 'truncated':
        return trunc_data.mean()
    elif type_ == 'winsorized':
        return np.clip(data, trunc_data.min(), trunc_data.max()).mean()

    
def binom_wilson_confidence_interval(p, n, confidence_level=0.95):
    """
    Calculates the Wilson confidence interval for a binomial proportion.

    This method provides a more accurate confidence interval for a binomial proportion, especially useful when the sample size is small or the proportion is close to 0 or 1.

    Parameters
    ----------
    p : float
        Observed proportion (successes / total).
    n : int
        Total number of observations (sample size).
    confidence_level : float, optional
        The desired confidence level for the interval (default is 0.95).

    Returns
    -------
    tuple
        A tuple containing the lower and upper bounds of the Wilson confidence interval.

    Notes
    -----
    The Wilson score interval is an improvement over the standard normal approximation, particularly for small sample sizes or extreme proportion values. 
    It adjusts the standard error to account for the uncertainty inherent in the estimation of a proportion.
    """
    z = st.norm.ppf(1 - (1 - confidence_level) / 2)
    a = p + (z**2 / (2 * n))
    b = z * (p * (1 - p) / n + z**2 / (4 * n**2))**0.5
    c = 1 + z**2 / n
    lower, upper = (a - b) / c, (a + b) / c
    return lower, upper

def get_lognormal_params(mean, std):
    """
    Function to estimate the parameters of a lognormal distribution.

    Methodology: Data is generated from a normal distribution with the given mean and 
    standard deviation. Then, the natural logarithm is taken from each data point.
    The mean and standard deviation of these log-transformed points are calculated 
    and returned as estimates of the lognormal distribution parameters.
    This approach corresponds to the Monte Carlo method for estimating statistical parameters.

    Parameters:
    mean (float): Mean value for generating the normal distribution.
    std (float): Standard deviation for generating the normal distribution.

    Returns:
    tuple: Estimates of the mean and standard deviation of the lognormal distribution.
    """
    dist = np.log(np.abs(np.random.normal(mean, std, size=1_000_000)))
    return dist.mean(), dist.std(ddof=1)

def jackknife_samples(sample):
    """
    Generate jackknife samples by systematically leaving out each observation from the dataset.

    Parameters
    ----------
    sample : array-like
        The original sample data.

    Returns
    -------
    ndarray
        Array of jackknife samples, each with one observation omitted.
        
    Notes
    -----
    Similar to https://docs.astropy.org/en/stable/api/astropy.stats.jackknife_resampling.html
    """
    return np.array([np.delete(sample, i) for i in range(len(sample))])
    
def jackknife_estim(sample, func=np.mean, confidence_level=0.95):
    """
    Perform jackknife resampling to estimate a parameter and its confidence interval.

    Parameters
    ----------
    sample : array-like
        The original sample data.
    func : function, default=np.mean
        The statistical function to apply to the sample and jackknife samples.
    confidence_level : float, default=0.95
        The confidence level for the confidence interval calculation.

    Returns
    -------
    dict
        A dictionary containing the estimated parameter ('estim'), bias, standard error ('se'), 
        and confidence interval ('ci').

    Notes
    -----
    Similar to https://docs.astropy.org/en/stable/api/astropy.stats.jackknife_stats.html
    """
    sample = np.asarray(sample)
    sample_size = sample.shape[0]
    z = st.norm.ppf(1 - (1 - confidence_level) / 2)
    stat = func(sample)
    jackknife_stats = np.array([func(np.delete(sample, i)) for i in range(sample_size)])
    mean_jacknife_stat = np.mean(jackknife_stats)
    bias = (sample_size-1) * (mean_jacknife_stat - stat)
    estim = stat - bias
    se = ((sample_size - 1) * np.mean((jackknife_stats - mean_jacknife_stat) ** 2)) ** .5
    return {'estim':estim, 'bias':bias, 'se':se, 'ci':(estim - z * se, estim + z * se)}

def bootstrap_ci(sample, func=np.mean, confidence_level=0.95, n_resamples=10000, method='percentile', return_dist=False, progress_bar=True, random_state=None):
    """
    Calculate bootstrap confidence intervals for a statistic of a sample.

    Parameters
    ----------
    sample : array-like
        The original sample data.
    func : function, default=np.mean
        The statistical function to apply to the sample and bootstrap samples.
    confidence_level : float, default=0.95
        The confidence level for the confidence interval calculation.
    n_resamples : int, default=10000
        The number of bootstrap resamples to generate.
    method : str, default='percentile'
        The bootstrap method to use ('percentile', 'pivotal', 'bca').
    return_dist : bool, default=False
        If True, returns the bootstrap sample distribution along with the CI.
    random_state : int, optional
        The seed for the random number generator.

    Returns
    -------
    tuple
        The lower and upper bounds of the confidence interval.

    Reference
    ---------
    http://users.stat.umn.edu/~helwig/notes/bootci-Notes.pdf

    Note
    ----
    Close to https://scipy.github.io/devdocs/reference/generated/scipy.stats.bootstrap.html
    """
    np.random.seed(random_state)
    sample = np.asarray(sample)
    sample_size = sample.shape[0]
    sample_stat = func(sample)
    lower, upper = (1 - confidence_level) / 2, 1 - (1 - confidence_level) / 2
    rng = tqdm(range(n_resamples)) if progress_bar else range(n_resamples)
    bootstrap_stats = []
    for i in rng:
        bootstrap_stats.append(func(sample[np.random.randint(0,sample_size,sample_size)]))
    
    if method == 'percentile':
        result = tuple(np.quantile(bootstrap_stats, q=[lower, upper]))
    elif method == 'pivotal':
        result = tuple(np.quantile(2*sample_stat - bootstrap_stats, q=[lower, upper]))
    elif method == 'bca':
        z0 = st.norm.ppf((np.sum(bootstrap_stats < sample_stat)) / n_resamples)
        rng = tqdm(range(sample_size)) if progress_bar else range(sample_size)
        jackknife_stats = np.array([func(np.delete(sample, i)) for i in rng])
        mean_jackknife_stats = np.mean(jackknife_stats)
        num = np.sum((mean_jackknife_stats - jackknife_stats) ** 3)
        denom = 6 * (np.sum((mean_jackknife_stats - jackknife_stats) ** 2) ** (3/2))
        acc = num / denom if denom != 0 else 0
        ppf_l, ppf_u = st.norm.ppf(lower), st.norm.ppf(upper)
        a_1 = st.norm.cdf(z0 + (z0 + ppf_l) / (1 - acc * (z0 + ppf_l)))
        a_2 = st.norm.cdf(z0 + (z0 + ppf_u) / (1 - acc * (z0 + ppf_u)))
        result = tuple(np.quantile(bootstrap_stats, q=[a_1,a_2]))
    else:
        raise ValueError(f'Passed {method}. Please use percentile, pivotal, or bca.')

    return (result, bootstrap_stats) if return_dist else result

class BootstrapWrapper:
    """
    A decorator class for applying bootstrap resampling to estimate confidence intervals 
    for statistics calculated from sample data.

    Attributes:
    -----------
    confidence_level : float, optional
        The confidence level for the confidence interval estimation. Default is 0.95.
    n_resamples : int, optional
        The number of bootstrap resamples to generate. Default is 10,000.
    random_state : int, optional
        Seed for the random number generator to ensure reproducibility. Default is None.
    return_dist : bool, optional
        If True, returns both the confidence interval and the resampled statistics distribution. Default is False.
    progress_bar : bool, optional
        If True, displays a progress bar during the bootstrap resampling. Default is True.

    Methods:
    --------
    __init__(self, confidence_level=0.95, n_resamples=10_000, random_state=None, return_dist=False, progress_bar=True)
        Initializes the BootstrapWrapper with specified attributes.

    _compute_ci(self, data)
        Computes the confidence interval from the bootstrap resampled statistics.

    _get_idx(size)
        Generates random indices for resampling, given the sample size.

    __call__(self, func)
        The main method that applies bootstrap resampling to the function `func` passed to the decorator.
        It wraps `func`, performing bootstrap resampling on its input data, and then applies `func`
        to each resampled dataset to compute the desired statistic.

    Usage example:
    --------------
    @BootstrapWrapper()
    def linear_reg_coef(x,y):
        return np.polyfit(x,y, deg=1)[1]

    # Now `linear_reg_coef` will return the 95% confidence interval of the slope coef based on bootstrap resampling.

    Raises:
    -------
    TypeError
        If any of the arguments passed to the decorated function is not iterable.
    """
    def __init__(self, confidence_level=0.95, n_resamples=10_000, random_state=None, return_dist=False, progress_bar=True):
        """Constructor for the BootstrapWrapper class"""
        self.n_resamples = n_resamples
        self.random_state = random_state
        self.lower, self.upper = (1 - confidence_level) / 2, 1 - (1 - confidence_level) / 2
        self.progress_bar = progress_bar
        self.return_dist = return_dist

    def _compute_ci(self, data):
        """
        Computes the confidence interval from the bootstrap statistics.

        Parameters:
        -----------
        data : array-like
            The bootstrap statistics from which to compute the confidence interval.

        Returns:
        --------
        tuple
            The lower and upper bounds of the confidence interval.
        """
        return np.quantile(data, q=[self.lower, self.upper], axis=0)
    
    @staticmethod
    def _get_idx(size):
        """
        Generates random indices for resampling.

        Parameters:
        -----------
        size : int
            The size of the sample from which to generate indices.

        Returns:
        --------
        ndarray
            An array of random indices.
        """
        return np.random.randint(low=0, high=size, size=size)
    
    def __call__(self, func):
        """
        The main decorator method that wraps the target function, applying bootstrap resampling to its arguments.

        Parameters:
        -----------
        func : callable
            The target function to which bootstrap resampling is applied.

        Returns:
        --------
        callable
            A wrapped version of the target function that applies bootstrap resampling.
        """
        def wrapper(*args, **kwargs):
            np.random.seed(self.random_state)
            rng = tqdm(range(self.n_resamples)) if self.progress_bar else range(self.n_resamples)
            self.stat_lst = []
            size_lst = []
            for arg in args:
                if not hasattr(arg, '__len__'):
                    raise TypeError('All args must be iterable')
                else:
                    size_lst.append(len(arg)) 
            size = min(size_lst)
            arrs = np.column_stack([i for i in args])
            for i in rng:
                idx = self._get_idx(size)
                sub = arrs[idx]
                sub_lst = [sub[:,i] for i in range(sub.shape[1])]
                self.stat_lst.append(func(*sub_lst, **kwargs))
            return (self._compute_ci(self.stat_lst), self.stat_lst) if self.return_dist else self._compute_ci(self.stat_lst)
        return wrapper
