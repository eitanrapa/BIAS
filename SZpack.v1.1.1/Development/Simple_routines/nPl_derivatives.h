//==================================================================================================
//
// Author: Jens Chluba 
// first implementation: April 2012
// last modification   : July  2012
//
//==================================================================================================

#ifndef NPL_DERIVATIVES_H
#define NPL_DERIVATIVES_H

using namespace std;

//==================================================================================================
double Pfunc(int k, double x);

//==================================================================================================
// 1-e^-x
//==================================================================================================
double one_minus_exp_mx(double x);
double one_minus_exp_mx(double x, double exp_mx);

//==================================================================================================
// x^k d^k nPl(x) / d^k x
//==================================================================================================
double xk_dk_nPl(int k, double x);

void dk_nPl_dks(int kmax, double x, vector<double> &results);
double Binomial_coeff(int n, int k);

#endif

//==================================================================================================
//==================================================================================================
