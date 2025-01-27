import numpy as np
import scipy.stats as st
import matplotlib.pyplot as plt
import seaborn as sns
from pystatlab.utility import ParallelResampler

class ParentTestInterface:
    """
    Base interface for conducting statistical tests, particularly for A/B testing.
    Provides foundational methods and attributes for subclass implementations.
    
    Parameters
    ----------
    confidence_level : float
        The confidence level for calculating confidence intervals.
    """
    
    init_items = {}

    def __init__(self, confidence_level):
        """
        Constructor for the ParentTestInterface class.
        """
        self.confidence_level = confidence_level
        self._compute_confidence_bounds()
        self.init_items = self.__dict__.copy()
        
    def __setattr__(self,key,value):
        """
        Custom attribute setter that updates confidence bounds when 
        'confidence_level' changes.

        Parameters
        ----------
        key : str
            The name of the attribute to be set or modified.
        value : various
            The value to be set for the attribute.
        """
        if key == 'confidence_level':
            super().__setattr__(key, value)
            self._compute_confidence_bounds()
        elif key == 'progress_bar' and self.__dict__.get('n_jobs') != 1:
            super().__setattr__(key, False) 
        else:
            super().__setattr__(key, value)

        if key == 'progress_bar' and self.init_items.get('n_jobs') != 1:
            self.init_items[key] = False
        elif key in self.init_items and self.init_items[key] != value:
            self.init_items[key] = value
        
    def _compute_confidence_bounds(self):
        """
        Internal method to compute the confidence bounds based on the given 
        confidence level.
        """
        self.left_quant, self.right_quant =  (1 - self.confidence_level) / 2, 1 - (1 - self.confidence_level) / 2
        
    def _compute_ci(self, data):
        """
        Computes confidence intervals for given data.

        Parameters
        ----------
        data : array-like
            The data for which confidence intervals are to be computed.

        Returns
        -------
        array-like
            Confidence intervals for the provided data.
        """
        return np.quantile(data, [self.left_quant, self.right_quant])
    
    @staticmethod    
    def _compute_uplift(before, after):
        """
        Calculates uplift, typically used for comparing metrics before and 
        after the test.

        Parameters
        ----------
        before : numeric
            The metric value before the test or for the control group.
        after : numeric
            The metric value after the test or for the test group.

        Returns
        -------
        numeric
            Computed uplift value.
        """
        return (after - before) / before
    
    def get_test_parameters(self):
        """
        Retrieves initial test parameters or settings.

        Returns
        -------
        dict
            Dictionary of initial test parameters.
        """
        return self.init_items
    
    @staticmethod
    def _get_alternative_value(p, two_sided):
        """
        Calculates p-value for two_sided tests.

        Parameters
        ----------
        p : float
            The original p-value.
        two_sided : bool
            A flag indicating if the test is two-sided.

        Returns
        -------
        float
            P-value based on the type of test.
        """
        pvalue = min(2*p,2-2*p)
        return pvalue if two_sided else p
    
    @staticmethod    
    def _get_readable_format(result_dict):
        """
        Prints the results in a human-readable format.

        Parameters
        ----------
        result_dict : dict
            A dictionary containing key statistical results.

        Notes
        -----
        Formats and prints the results, such as p-values, confidence intervals, 
        and uplift metrics, in a readable percentage format.
        """
        for k, i in result_dict.items():
            if k in ('uplift','proba','test_loss', 'control_loss'):
                print('{}: {:.3%}'.format(k,i))
            elif k == 'uplift_ci':
                i = list(map(lambda x: '{:.3%}'.format(x),i))
                print(f'{k}: {i[0]} - {i[1]}')
            else:
                print(f'{k}: {i}')
    
    @staticmethod
    def _metric_distributions_chart(control_metric, test_metric, title):
        """
        Draws a histogram chart for the distributions of control and test metrics.

        Parameters
        ----------
        metric_a : array-like
            Data points for the control group.
        metric_b : array-like
            Data points for the test group.
        title : str
            The title of the chart.
        """
        sns.kdeplot(control_metric, common_norm=True, fill=True, color='#19D3F3', label='Control')
        sns.kdeplot(test_metric, common_norm=True, fill=True, color='C1', label='Test')
        plt.title(title)
        plt.legend()
        
    @staticmethod    
    def _uplift_distribtuion_chart(uplift_distribution, uplift):
        """
        Draws a cumulative distribution chart for uplift.

        Parameters
        ----------
        uplift_distribution : array-like
            Data points for the uplift distribution.
        uplift : float
            The computed uplift value.
        """
        thresh = 0
        x=np.sort(uplift_distribution)
        y=np.arange(x.shape[0]) / x.shape[0]
        
        plt.plot(x, y, color='black', alpha=0.5) 
        plt.axvline(x=uplift, color='black', linestyle='--')
        plt.fill_between(x, y, where=(x > thresh), color='#89CFF0', alpha=0.5, interpolate=True)  
        plt.fill_between(x, y, where=(x < thresh), color='#EF553B', alpha=0.5, interpolate=True)  
        plt.title('Uplift ECDF')
        plt.ylabel('probability')
                
    def resample():
        """
        Abstract method to be implemented in subclasses. Used for resampling 
        in statistical tests.
        """
        raise NotImplementedError("Subclasses should implement this!")
        
    def compute():
        """
        Abstract method to be implemented in subclasses. Used for computing 
        test results.
        """
        raise NotImplementedError("Subclasses should implement this!")
    
    def get_charts():
        """
        Abstract method to be implemented in subclasses. Used for generating 
        charts related to the test results.
        """
        raise NotImplementedError("Subclasses should implement this!")

class BayesBeta(ParentTestInterface):
    """
    Implements Bayesian approach to A/B testing using beta distributions.

    This class extends ParentTestInterface, adding specific methods for Bayesian analysis.
    
    Parameters
    ----------
    confidence_level : float, default=0.95
        The confidence level for calculating confidence intervals.
    n_resamples : int, default=100000
        The number of simulations for generating distributions.
    random_state : int, optional
        The seed for the random number generator to ensure reproducibility.
    """

    def __init__(self, confidence_level=0.95, n_resamples=100000, random_state=None):
        """
        Constructor for the BayesBeta class.
        """
        self.n_resamples=n_resamples
        self.random_state=random_state
        super().__init__(confidence_level=confidence_level)
            
    def resample(self, nobs, counts, prior=()):
        """
        Generates beta distributions for control and test groups based on observations and prior data.

        Parameters
        ----------
        nobs : list of int, length=2
            The number of successes in the control and test groups, respectively.
        counts : list of int, length=2
            The total number of trials in the control and test groups, respectively.
        prior : tuple or list, default=()
            The prior parameters for the beta distributions. It can be a tuple or list of two or four elements.

        Returns
        -------
        dict
            Dictionary of updated test parameters after resampling.
        """
        if len(nobs) != 2 or len(counts) !=2:
            raise ValueError('You must have 2 elements in each list')
            
        control_a, test_a = nobs
        control_total, test_total = counts
        control_b, test_b = control_total - control_a, test_total - test_a

        np.random.seed(self.random_state)
        
        self.cr_control = control_a / control_total
        self.cr_test = test_a / test_total
        self.uplift = self._compute_uplift(self.cr_control,self.cr_test)
        
        if not isinstance(prior, (list,tuple)):
            raise TypeError(f'You can use for prior only list or tuple. Passed {type(prior).__name__}')
        elif not prior:
            pr = (1,) * 4
        elif len(prior) == 2:
            pr = prior * 2
        elif len(prior) in [1,3] or len(prior) > 4:
            raise ValueError('You can pass only two or four values')
        else:
            pr = prior
  
        self.beta_control = np.random.beta(a=control_a+pr[0],b=control_b+pr[1],size=self.n_resamples)
        self.beta_test = np.random.beta(a=test_a+pr[2],b=test_b+pr[3],size=self.n_resamples)  
        self.uplift_dist = self._compute_uplift(self.beta_control, self.beta_test)
        self.uplift_ci = self._compute_ci(self.uplift_dist)
        return self.get_test_parameters()
        
    def compute(self, two_sided=False, readable=False):
        """
        Calculates statistical significance and other metrics.

        Parameters
        ----------
        two_sided : bool, default=False
            Determines if the test is two-sided. If False, a one-sided test is performed.
        readable : bool, default=False
            If True, prints the results in a readable format.

        Returns
        -------
        dict
            Dictionary of computed metrics, including significance information, uplift, control loss, and test loss.
        """
        control_loss = np.mean(np.maximum(self.uplift_dist, 0)) #uplift_loss_c
        test_loss = np.mean(np.maximum(self._compute_uplift(self.beta_test, self.beta_control),0)) #uplift_loss_t
        
        p = self._get_alternative_value(p=np.mean(self.beta_test > self.beta_control), two_sided=two_sided)
        significance_result = {'proba':p} if not two_sided else {'pvalue':p}
            
        result = {
            **significance_result, 
            'uplift': self.uplift, 
            f'uplift_ci': self.uplift_ci, 
            'control_loss': control_loss, 
            'test_loss': test_loss
        }
        
        return self._get_readable_format(result_dict=result) if readable else result
                
    def get_charts(self, figsize=(22,6)):
        """
        Generates and displays charts visualizing the resampling results.

        Parameters
        ----------
        figsize : tuple of int, default=(22, 6)
            The size of the figure to be displayed.
        """
        with sns.axes_style('whitegrid'):
            plt.figure(figsize=figsize)
            plt.subplot(1,3,1)
            self._metric_distributions_chart(control_metric=self.beta_control, 
                                             test_metric=self.beta_test, 
                                             title='Beta Distributions for CR', 
                                             )
            
            plt.subplot(1,3,2)
            sns.histplot(x=self.beta_control,y=self.beta_test,bins=50, color='#3366CC')
            plt.xlabel('control')
            plt.ylabel('test')
            min_xy, max_xy = np.min([self.beta_control, self.beta_test]), np.max([self.beta_control, self.beta_test])
            plt.axline(xy1=[min_xy, min_xy], xy2=[max_xy,max_xy], color='black', linestyle='--')
            plt.title('Joint Distribution')
            plt.subplot(1,3,3)
            self._uplift_distribtuion_chart(uplift_distribution=self.uplift_dist, 
                                            uplift=self.uplift, 
                                            )
            plt.show()

class Bootstrap(ParentTestInterface):
    """
    Bootstrap class for conducting statistical tests using bootstrapping.

    This class extends ParentTestInterface, providing a resampling method
    to estimate the distribution of a statistic by randomly sampling with replacement.
    """
    def __init__(self, func=np.mean, confidence_level=0.95, n_resamples=10_000, random_state=None, n_jobs=-1, progress_bar=False):
        """
        Initializes the Bootstrap class with the specified parameters.
    
        Parameters
        ----------
        func : function, default=np.mean
            The statistical function to apply to the samples.
        confidence_level : float, default=0.95
            The confidence level for calculating confidence intervals.
        n_resamples : int, default=10000
            The number of resampling iterations to perform.
        random_state : int, optional
            The seed for the random number generator to ensure reproducibility.
        n_jobs : int, default=-1
            The number of jobs to run in parallel during resampling. Use -1 to utilize all available cores.
        progress_bar : bool, default=False
            Whether to display a progress bar during resampling. Only effective if `n_jobs` is set to 1.
        """
        self.func = func
        self.n_resamples = n_resamples
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.progress_bar = False if n_jobs != 1 else progress_bar
        super().__init__(confidence_level=confidence_level)

    def resample(self, *samples, match_max_length=False, ind=True):
        """
        Performs the resampling process on the given samples.

        Parameters
        ----------
        *samples : array-like
            The samples to be resampled. For non-ratio metrics, two samples should be provided.
            For ratio metrics, four samples should be provided: numerator and denominator for control,
            then for treatment groups.
        match_max_length : bool, default=False
            If True, bootstrap samples are created with a size equal to the maximum length between the control and test groups.
            If False, bootstrap samples maintain the original proportion sizes of the groups.
            Note: When `ind` is False, `match_max_length` has no effect.
        ind : bool, default=True
            Whether the samples are independent.
    
        Returns
        -------
        dict
            A dictionary containing the test parameters after resampling.
    
        Raises
        ------
        ValueError
            If the number of samples provided is not equal to 2 for non-ratio metrics,
            or not equal to 4 for ratio metrics.
            If the lengths of numerators and denominators do not match for ratio metrics.
        """

        def _generate_indices(seed, size_a, size_b, ind, match_max_length):
            if match_max_length:
                sample_size_a = sample_size_b = max(size_a, size_b)
            else:
                sample_size_a, sample_size_b = size_a, size_b
            a = seed.integers(low=0, high=size_a, size=sample_size_a)
            if not ind:
                return a, a
            else:
                b = seed.integers(low=0, high=size_b, size=sample_size_b)
                return a, b
            
        def _rel_size_comrarison(size_a, size_b):
            if not ind and size_a != size_b:
                raise ValueError('Relative samples must be same sample size')

        if len(samples) == 2:
            sample_a, sample_b = np.asarray(samples[0]), np.asarray(samples[1])
            size_a, size_b = sample_a.shape[0], sample_b.shape[0]
            _rel_size_comrarison(size_a, size_b)
            self.uplift = self._compute_uplift(self.func(sample_a), self.func(sample_b))
        elif len(samples) == 4:
            if len(samples[0]) != len(samples[1]) or len(samples[2]) != len(samples[3]):
                raise ValueError(
                    "Numerator and denominator must be the same length"
                )
        
            numerator_a, denominator_a = np.asarray(samples[0]), np.asarray(samples[1])
            numerator_b, denominator_b = np.asarray(samples[2]), np.asarray(samples[3])
            sample_a = np.column_stack((numerator_a, denominator_a))
            sample_b = np.column_stack((numerator_b, denominator_b))

            def func(sample):
                return np.sum(sample[:, 0]) / np.sum(sample[:, 1])

            self.func = func
            size_a, size_b = numerator_a.shape[0], numerator_b.shape[0]
            _rel_size_comrarison(size_a, size_b)                
            self.uplift = self._compute_uplift(self.func(sample_a),self.func(sample_b))
        else:
            raise ValueError(
                "You must pass only two samples for non-ratio metrics, or four samples for ratio metrics: "
                "numerator and denominator for control, then for treatment groups"
            )
            
        def _resample_func(seed):
            ids_a, ids_b = _generate_indices(seed, size_a=size_a, size_b=size_b, ind=ind, match_max_length=match_max_length)
            return [self.func(sample_a[ids_a]),self.func(sample_b[ids_b])]

        pr = ParallelResampler(n_resamples=self.n_resamples, random_state=self.random_state, n_jobs=self.n_jobs, progress_bar=self.progress_bar)
        self._resample_data = pr.resample(_resample_func)
            
        self.diffs = self._resample_data[:, 1] - self._resample_data[:, 0]
        self.a_ci = self._compute_ci(self._resample_data[:, 0])
        self.b_ci = self._compute_ci(self._resample_data[:, 1])
        self.diff_ci = self._compute_ci(self.diffs)
        self.uplift_dist = self._compute_uplift(self._resample_data[:, 0], self._resample_data[:, 1])
        self.uplift_ci = self._compute_ci(self.uplift_dist)
        if self.n_jobs != 1:
            pr.elapsed_time()
        return self.get_test_parameters()

    def compute(self, two_sided=True, readable=False):
        """
        Computes the statistical significance and other metrics.
    
        Parameters
        ----------
        two_sided : bool, default=True
            Whether to perform a two-sided test.
        readable : bool, default=False
            Whether to print results in a human-readable format.
    
        Returns
        -------
        dict
            A dictionary of computed metrics, including p-value, uplift, confidence intervals for control and test groups,
            and the difference confidence interval.
        """
        p = (np.sum(self._resample_data[:, 1] > self._resample_data[:, 0]) + 1) / (self.n_resamples + 1)
        pvalue = self._get_alternative_value(p=p, two_sided=two_sided)

        result = {
            'pvalue': pvalue,
            'uplift': self.uplift,
            'uplift_ci': self.uplift_ci,
            'control_ci':self.a_ci,
            'test_ci':self.b_ci,
            'diff_ci': self.diff_ci
        }
        
        return self._get_readable_format(result_dict=result) if readable else result

    def get_charts(self, figsize=(22, 6)):
        """
        Generates and displays charts visualizing the resampling results.
    
        Parameters
        ----------
        figsize : tuple of int, default=(22, 6)
            The size of the figure to be displayed.
    
        Displays
        -------
        Plots
            Three plots visualizing the distribution of the resampled metrics for control and test groups,
            the distribution of differences between test and control, and the uplift distribution.
        """
        with sns.axes_style('whitegrid'):
            plt.figure(figsize=figsize)
            plt.subplot(1,3,1)
            self._metric_distributions_chart(control_metric=self._resample_data[:, 0],
                                             test_metric=self._resample_data[:, 1],
                                             title=f'Distribution of {self.func.__name__}(s) for each group',
                                             )
            
            plt.subplot(1, 3, 2)
            bar = sns.kdeplot(self.diffs, fill=True, color='#DAA520')
            plt.title(f'Distribution of {self.func.__name__}(s) differences (Test-Control)')
            plt.subplot(1,3,3)
            self._uplift_distribtuion_chart(uplift_distribution=self.uplift_dist, 
                                            uplift=self.uplift, 
                                            )
            plt.show()


class QuantileBootstrap(ParentTestInterface):
    """
    Efficient implementation of the quantile comparison method using bootstrap resampling,
    as described in the Spotify Engineering article. This class is designed for large-scale 
    A/B testing scenarios, where traditional bootstrap methods may be computationally intensive.
    
    Reference:
    https://engineering.atspotify.com/2022/03/comparing-quantiles-at-scale-in-online-a-b-testing/

    Parameters
    ----------
    q : float, default=0.5
        The target quantile for comparison between samples.
    confidence_level : float, default=0.95
        The confidence level for calculating confidence intervals.
    n_resamples : int, default=100000
        The number of bootstrap samples to generate.
    random_state : int, optional
        The seed for the random number generator to ensure reproducibility.
    """
    def __init__(self, q=0.5, confidence_level=0.95, n_resamples=100_000, random_state=None):
        """
        Constructor for the QuantileBootstrap class.
        """
        self.q = q
        self.n_resamples=n_resamples
        self.random_state=random_state
        super().__init__(confidence_level=confidence_level)
    
    def resample(self, *samples):
        """
        Performs resampling to estimate the quantile distribution.

        This method applies a Poisson bootstrap algorithm to resample the provided datasets
        and estimate the distribution of the specified quantile, allowing for comparison between
        the two samples. It raises a ValueError if exactly two samples are not provided.

        Parameters
        ----------
        *samples : array-like
            The samples to be resampled for quantile comparison.
        """
        if len(samples) != 2:
            raise ValueError('You must pass only two samples')
            
        np.random.seed(self.random_state)
        
        sample_a, sample_b = np.sort(np.asarray(samples[0])), np.sort(np.asarray(samples[1]))
        self.resample_a = sample_a[np.random.binomial(p=self.q,n=sample_a.shape[0]+1, size=self.n_resamples)]
        self.resample_b = sample_b[np.random.binomial(p=self.q,n=sample_b.shape[0]+1, size=self.n_resamples)]
    
        self.uplift = self._compute_uplift(*np.quantile(a=[sample_a, sample_b], q=self.q, axis=1))
        self.diffs = self.resample_b - self.resample_a
        self.a_ci = self._compute_ci(self.resample_a)
        self.b_ci = self._compute_ci(self.resample_b)
        self.diff_ci = self._compute_ci(self.diffs)
        self.uplift_dist = self._compute_uplift(self.resample_a, self.resample_b)
        self.uplift_ci = self._compute_ci(self.uplift_dist)
        return self.get_test_parameters()
    
    def compute(self, two_sided=True, readable=False):
        """
        Computes the statistical significance of the quantile comparison.

        Parameters
        ----------
        two_sided : bool, default=True
            Whether to perform a two-sided test.
        readable : bool, default=False
            Whether to print the results in a human-readable format.
        """
        p = (np.sum(self.resample_b > self.resample_a) + 1) / (self.n_resamples + 1)
        pvalue = self._get_alternative_value(p=p, two_sided=two_sided)
        
        result = {
            'pvalue': pvalue,
            'uplift': self.uplift,
            'uplift_ci': self.uplift_ci,
            'control_ci':self.a_ci,
            'test_ci':self.b_ci,
            'diff_ci': self.diff_ci
        }
        
        return self._get_readable_format(result_dict=result) if readable else result
        
    def get_charts(self, figsize=(22, 6)):
        """
        Generates and displays charts visualizing the resampling results.

        Parameters
        ----------
        figsize : tuple of int, default=(22, 6)
            The size of the figure to be displayed.
        """
        with sns.axes_style('whitegrid'):
            plt.figure(figsize=figsize)
            plt.subplot(1,3,1)
            self._metric_distributions_chart(control_metric=self.resample_a,
                                             test_metric=self.resample_b,
                                             title=f'Distribution of q {self.q} for each group',
                                             )
            
            plt.subplot(1, 3, 2)
            bar = sns.kdeplot(self.diffs, fill=True, color='#DAA520')
            plt.title(f'Distribution of q {self.q} differences (Test-Contol)')
            plt.subplot(1,3,3)
            self._uplift_distribtuion_chart(uplift_distribution=self.uplift_dist, 
                                            uplift=self.uplift, 
                                            )
            plt.show()  


class ResamplingTtest(ParentTestInterface):
    """
    A class for conducting t-distribution-based resampling tests in A/B testing scenarios. This class
    generates samples distributed according to the t-distribution, ideal for situations where the 
    normal distribution assumption may not hold, such as with smaller sample sizes. It accounts for 
    variability in variances and is particularly suitable when dealing with unequal variances between groups.

    Inherits from ParentTestInterface to utilize common functionalities in A/B testing analysis.

    Parameters
    ----------
    confidence_level : float, default=0.95
        The confidence level for calculating confidence intervals.
    n_resamples : int, default=100000
        The number of resampling iterations to perform.
    random_state : int, optional
        The seed for the random number generator to ensure reproducibility.
    """
    def __init__(self, confidence_level=0.95, n_resamples=100_000, random_state=None):
        """
        Constructor for the ParametricResamplingTest class.
        """
        self.n_resamples=n_resamples
        self.random_state=random_state
        super().__init__(confidence_level=confidence_level)
        
    def resample(self, mean, std, n):
        """
        Performs the resampling process using a t-distribution approach. This method simulates resampling
        by generating t-distributed random variables, allowing for the consideration of variability in variances
        across samples.

        Parameters
        ----------
        mean : list of float, length=2
            The means of the two samples to be compared.
        std : list of float, length=2
            The standard deviations of the two samples.
        n : list of int, length=2
            The sample sizes of the two groups.

        Raises
        ------
        ValueError
            If the length of any input list is not equal to 2.
        """
        if len(mean) != 2 or len(std) != 2 or len(n) != 2:
            raise ValueError('Len of all collections must be equal to 2')
    
        mean, std, self.n = np.asarray(mean),np.asarray(std),np.asarray(n)
        self.sem = std / self.n**.5
        self.delta_mean = mean[1]-mean[0]
        self.delta_sem = (self.sem[0]**2+self.sem[1]**2)**.5
        
        np.random.seed(self.random_state)
        
        self.resample_a = st.t.rvs(loc=mean[0],scale=self.sem[0], df=self.n[0]-1, size=self.n_resamples)
        self.resample_b = st.t.rvs(loc=mean[1],scale=self.sem[1], df=self.n[1]-1, size=self.n_resamples)
        
        self.uplift = self._compute_uplift(mean[0],mean[1])
        self.diffs = self.resample_b - self.resample_a
        self.a_ci = st.t.interval(confidence=self.confidence_level, loc=mean[0],scale=self.sem[0], df=self.n[0]-1)
        self.b_ci = st.t.interval(confidence=self.confidence_level, loc=mean[1],scale=self.sem[1], df=self.n[1]-1)
        self.diff_ci = self._compute_ci(self.diffs)
        self.uplift_dist = self._compute_uplift(self.resample_a, self.resample_b)
        self.uplift_ci = self._compute_ci(self.uplift_dist)
        return self.get_test_parameters()
            
    def compute(self, two_sided=True, readable=False, equal_var=False):
        """
        Computes the statistical significance of the comparison based on t-distribution using an analytical approach.
        This method enhances the accuracy and efficiency of p-value calculations.

        Parameters
        ----------
        two_sided : bool, default=True
            Whether to perform a two-sided test.
        readable : bool, default=False
            Whether to output results in a human-readable format.
        equal_var : bool, default=False
            Whether to assume equal variances for the calculation of degrees of freedom.

        Returns
        -------
        dict
            A dictionary of computed metrics including p-value and uplift metrics.
        """
        if equal_var:
            self.df = self.n.sum()-2
        else:
            self.df = (self.sem[0]**2 + self.sem[1]**2)**2 / ((self.sem[0]**4 / (self.n[0] - 1)) + (self.sem[1]**4 / (self.n[1] - 1))) 
        p = st.t.cdf(x=0, loc=self.delta_mean, scale=self.delta_sem, df=self.df)
        pvalue = self._get_alternative_value(p=p, two_sided=two_sided)
        
        result = {
            'pvalue': pvalue,
            'uplift': self.uplift,
            'uplift_ci': self.uplift_ci,
            'control_ci':self.a_ci,
            'test_ci':self.b_ci,
            'diff_ci': self.diff_ci,
            'df':self.df
        }
        
        return self._get_readable_format(result_dict=result) if readable else result
                    
    def get_charts(self, figsize=(22, 6)):
        """
        Generates and displays charts for visualizing the resampling results.

        Parameters
        ----------
        figsize : tuple of int, default=(22, 6)
            The size of the figure to be displayed.
        """
        with sns.axes_style('whitegrid'):
            plt.figure(figsize=figsize)
            plt.subplot(1,3,1)
            self._metric_distributions_chart(control_metric=self.resample_a,
                                             test_metric=self.resample_b,
                                             title=f'Distribution of Mean(s) for each group',
                                             )
            
            plt.subplot(1, 3, 2)
            bar = sns.kdeplot(self.diffs, fill=True, color='#DAA520')
            plt.title(f'Distribution of Mean(s) differences (Test-Control)')
            plt.subplot(1,3,3)
            self._uplift_distribtuion_chart(uplift_distribution=self.uplift_dist, 
                                            uplift=self.uplift, 
                                            )
            plt.show()


def permutation_ind(*samples,
                    func=np.mean, 
                    confidence_level=0.95,
                    n_resamples=10000,
                    two_sided=True, 
                    n_jobs=-1,
                    random_state=None, 
                    progress_bar=False, 
                    ):
    """
    Performs an independent two-sample permutation test.

    This test evaluates whether there is a significant difference between 
    the distributions of two independent samples by comparing their test statistics.
    It is suitable for non-normal distributions and is robust to the presence of outliers.

    Parameters
    ----------
    samples : tuple of array-like
        The samples to compare. For non-ratio metrics, provide two samples.
        For ratio metrics, provide four samples: numerator and denominator for 
        control, then for treatment groups.
    func : function, default=np.mean
        Function used to compute the test statistic (e.g., np.mean, np.median).
        This parameter is ignored when four samples (ratio metrics) are provided.
    confidence_level : float, default=0.95
        The confidence level for the confidence interval of the difference.
    n_resamples : int, default=10000
        The number of permutations to perform during the test.
    two_sided : bool, default=True
        If True, performs a two-sided test; otherwise, performs a one-sided test.
    n_jobs : int, default=-1
        The number of jobs to run in parallel. Use -1 to utilize all available cores.
    random_state : int, optional
        Seed for the random number generator to ensure reproducibility.
    progress_bar : bool, default=False
        Whether to display a progress bar during resampling. Effective only if `n_jobs` is 1.

    Returns
    -------
    dict
        A dictionary containing the following keys:
        - 'pvalue': The p-value of the test.
        - 'uplift': The relative difference between the means of the samples.
        - 'diff': The observed difference between the test statistic of the samples.
        - 'permutation_diff_ci': Confidence interval of the permutation differences.

    Raises
    ------
    ValueError
        If the number of samples provided is not equal to 2 for non-ratio metrics,
        or not equal to 4 for ratio metrics.
        If the lengths of numerators and denominators do not match for ratio metrics.
    """
    pr = ParallelResampler(n_resamples=n_resamples, 
                           random_state=random_state, 
                           n_jobs=n_jobs, 
                           progress_bar=progress_bar)
    left_quant, right_quant =  (1 - confidence_level) / 2, 1 - (1 - confidence_level) / 2
    
    if len(samples) == 2:
        sample_a, sample_b = np.asarray(samples[0]), np.asarray(samples[1]) 
        
    elif len(samples) == 4:            
        if len(samples[0]) != len(samples[1]) or len(samples[2]) != len(samples[3]):
            raise ValueError(
                "Numerator and denominator must be the same length"
            )
        
        numerator_a, denominator_a = np.asarray(samples[0]), np.asarray(samples[1])
        numerator_b, denominator_b = np.asarray(samples[2]), np.asarray(samples[3])
        
        sample_a = np.column_stack((numerator_a, denominator_a))
        sample_b = np.column_stack((numerator_b, denominator_b))

        def func(sample):
            return np.sum(sample[:, 0]) / np.sum(sample[:, 1])
    else:
        raise ValueError(
            "You must pass only two samples for non-ratio metrics, or four samples for ratio metrics: "
            "numerator and denominator for control, then for treatment groups"
        )

    observed_diff = func(sample_b) - func(sample_a)
    uplift = observed_diff / func(sample_a)
    
    combined = np.concatenate((sample_a, sample_b), axis=0)
    size_a = sample_a.shape[0]
    size_combined = combined.shape[0]
    
    indices = np.arange(size_combined)
    
    def _resample_func(seed):
        ids = seed.permutation(indices)
        perm_sample_a = combined[ids[:size_a]]
        perm_sample_b = combined[ids[size_a:]]
        return func(perm_sample_b) - func(perm_sample_a)

    
    diff_arr = pr.resample(_resample_func)

    p = (np.sum(observed_diff > diff_arr) + 1) / (n_resamples + 1)
    pvalue = min(2 * p, 2 - 2 * p) if two_sided else p
    permutation_diff_ci = np.quantile(diff_arr, q=[left_quant, right_quant])
    if n_jobs != 1:
        pr.elapsed_time()
    return {'pvalue': pvalue, 'uplift': uplift, 'diff': observed_diff, 'permutation_diff_ci': permutation_diff_ci}


def permutation_did(*values, group_label, experiment_stage_label, ratio=False, two_sided=True, n_resamples=10_000, random_state=None):
    """
    Performs permutation-based Difference-in-Differences analysis on given data.

    Parameters
    ----------
    values : tuple of array-like
        The data to analyze. For ratio metrics, pass two data columns (numerator and denominator). 
        For non-ratio metrics, pass one sample of data.
    group_label : array-like
        An array indicating group membership (e.g., treatment vs control).
    experiment_stage_label : array-like
        An array indicating the stage of the experiment (e.g., before vs after intervention).
    ratio : bool, default=False
        If True, analyze ratio metrics. If False, analyze non-ratio metrics.
    two_sided : bool, default=True
        If True, perform a two-sided test. If False, perform a one-sided test.
    n_resamples : int, default=10000
        Number of permutations to use in the analysis.
    random_state : int, optional
        Seed for the random number generator.

    Returns
    -------
    dict
        A dictionary containing the calculated difference-in-differences statistic ('stat')
        and the associated p-value ('pvalue').

    Raises
    ------
    ValueError
        If the sizes of the arrays do not match or the incorrect number of arrays are provided for the specified metric type.

    Reference
    ---------
    Detailed explanation and examples of the Difference-in-Differences analysis can be found in the article:
    "How to Accurately Test Significance with Difference-in-Difference Models" available at:
    https://engineering.atspotify.com/2023/09/how-to-accurately-test-significance-with-difference-in-difference-models/
    """
    group_label, experiment_stage_label = np.asarray(group_label), np.asarray(experiment_stage_label)
    
    if ratio:
        if len(values) != 2:
            raise ValueError('For ratio metrics you must use two data columns: numerator and denominator')
        else:
            numerator, denominator = np.asarray(values[0]), np.asarray(values[1])
            if not ((denominator.shape[0] == numerator.shape[0]) and (numerator.shape[0] == group_label.shape[0]) and (group_label.shape[0] == experiment_stage_label.shape[0])):
                raise ValueError('All arrays must have the same size')
    elif not ratio:
        if len(values) != 1:
            raise ValueError('For non-ratio metrics you must use one sample of data')
        else:
            values = np.asarray(values[0])
            if not ((values.shape[0] == group_label.shape[0]) and (group_label.shape[0] == experiment_stage_label.shape[0])):
                raise ValueError('All arrays must have the same size')
                
    
    def _groupby(values, group_label, experiment_stage_label):
        data = {}
        for i in sorted(set(group_label)):
            data.setdefault(i,[])
            for j in sorted(set(experiment_stage_label)):
                data[i].append(np.sum(values[np.where((group_label == i) & (experiment_stage_label == j))]))
        return np.array(list(data.values()))
    
    def _compute_did(grouped_data):
        delta_between_stages = grouped_data[:,1]-grouped_data[:,0]
        return delta_between_stages[1]-delta_between_stages[0]
    
    np.random.seed(random_state)
    
    stat = []
    if not ratio:
        true_did = _compute_did(_groupby(values, group_label, experiment_stage_label))
        for i in range(n_resamples):
            stat.append(_compute_did(_groupby(values, np.random.permutation(group_label), experiment_stage_label)))
    else:
        grouped_num = _groupby(numerator, group_label, experiment_stage_label)
        grouped_denom = _groupby(denominator, group_label, experiment_stage_label)
        true_did = _compute_did(grouped_num / grouped_denom)        
        for i in range(n_resamples):
            perm_data = np.random.permutation(group_label)
            grouped_num = _groupby(numerator, perm_data, experiment_stage_label)
            grouped_denom = _groupby(denominator, perm_data, experiment_stage_label)
            stat.append(_compute_did(grouped_num / grouped_denom))
            
    p = (np.sum(true_did > stat) + 1) / (n_resamples + 1) 
    pvalue = min(2*p, 2-2*p) if two_sided else p
    
    return {'stat': true_did, 'pvalue': pvalue}

def g_squared(contingency_table):
    """
    Calculates the G-squared (log-likelihood ratio) statistic and its p-value for a given contingency table.

    This function is used to test the independence of two categorical variables represented in the contingency table. 
    It is an alternative to the chi-squared test and is particularly useful for large sample sizes or when the data 
    is sparse.

    Parameters
    ----------
    contingency_table : array-like
        A two-dimensional array-like structure representing the contingency table. Rows represent one categorical variable, 
        and columns represent another categorical variable.

    Returns
    -------
    dict
        A dictionary with two keys:
        - 'pvalue': The p-value for the G-squared statistic, indicating the probability of observing the data if the null 
          hypothesis of independence is true.
        - 'g_squared': The computed G-squared statistic, a measure of divergence between the observed and expected frequencies.

    Notes
    -----
    The function first converts the input table to a NumPy array. It then computes the expected frequencies and degrees of 
    freedom using chi-squared contingency analysis. The G-squared statistic is calculated, followed by its p-value using 
    the survival function of the chi-squared distribution.
    """
    ct = np.asarray(contingency_table)
    _, _, dof,exp_freq = st.chi2_contingency(ct)
    g_squared = 2 * np.sum(ct * np.log(ct/exp_freq))
    return {'pvalue': st.chi2.sf(g_squared,dof), 'g_squared': g_squared}

def ttest_confidence_interval(*samples, confidence_level=0.95) -> dict:
    """
    Calculates the confidence interval for the difference between means of two samples using a t-test.

    This function computes the confidence interval for the difference in means (uplift) between two independent samples 
    assuming equal variance. It's useful for understanding the range within which the true mean difference lies with 
    a specified level of confidence.

    Parameters
    ----------
    samples : tuple of array-like
        The two samples for which the confidence interval of the difference between means is to be calculated.
        Only two samples should be provided.
    confidence_level : float, default=0.95
        The confidence level for the interval. The default is 0.95, representing a 95% confidence level.

    Returns
    -------
    dict
        A dictionary containing:
        - 'uplift_ci': The confidence interval for the relative uplift (percentage change) in mean from the first to 
          the second sample.
        - 'diff_ci': The absolute difference in means' confidence interval between the two samples.

    Raises
    ------
    ValueError
        If the number of samples provided is not equal to 2.

    Notes
    -----
    The function assumes that the two samples have equal variances and are independent. It uses the Student's t-distribution 
    to calculate the critical t-value and then computes the confidence interval for the difference in means.
    """
    if len(samples) != 2:
        raise ValueError('You must pass only two samples')
        
    a, b = np.asarray(samples[0]), np.asarray(samples[1])
    m_a, m_b = np.mean(a), np.mean(b)
    std_a, std_b = np.std(a, ddof=1), np.std(b, ddof=1)
    n_a, n_b = a.shape[0], b.shape[0]
    t = st.t.ppf(1-(1-confidence_level) / 2, df = n_a + n_b - 2)
    diff = m_b - m_a
    lower = diff - t * (std_a**2 / n_a + std_b**2 / n_b)**.5
    upper = diff + t * (std_a**2 / n_a + std_b**2 / n_b)**.5
    return {'uplift_ci': [lower / m_a, upper / m_a], 'diff_ci':[lower,upper]}
