#include <string.h>
#include <stdlib.h>
#include "sigtools.h"

static int elsize[] = {sizeof(char),
		       sizeof(unsigned char),
		       sizeof(signed char),
		       sizeof(short),
		       sizeof(int),
		       sizeof(long),
		       sizeof(float),
		       sizeof(double),
		       2*sizeof(float),
		       2*sizeof(double),
                       0};

typedef void (OneMultAddFunction) (char *, char *, char *);

#define MAKE_ONEMULTADD(fname, type) \
static void fname ## _onemultadd(char *sum, char *term1, char *term2) { \
  (*((type *) sum)) += (*((type *) term1)) * \
  (*((type *) term2)); return; }

MAKE_ONEMULTADD(UCHAR, unsigned char)
MAKE_ONEMULTADD(SCHAR, signed char)
MAKE_ONEMULTADD(SHORT, short)
MAKE_ONEMULTADD(INT, int)
MAKE_ONEMULTADD(LONG, long)
MAKE_ONEMULTADD(FLOAT, float)
MAKE_ONEMULTADD(DOUBLE, double)
 
#ifdef __GNUC__
MAKE_ONEMULTADD(CFLOAT, __complex__ float)
MAKE_ONEMULTADD(CDOUBLE, __complex__ double)
#else
#define MAKE_C_ONEMULTADD(fname, type) \
static void fname ## _onemultadd(char *sum, char *term1, char *term2) { \
  ((type *) sum)[0] += ((type *) term1)[0] * ((type *) term2)[0] \
    - ((type *) term1)[1] * ((type *) term2)[1]; \
  ((type *) sum)[1] += ((type *) term1)[0] * ((type *) term2)[1] \
    + ((type *) term1)[1] * ((type *) term2)[0]; \
  return; }
MAKE_C_ONEMULTADD(CFLOAT, float)
MAKE_C_ONEMULTADD(CDOUBLE, double)
#endif /* __GNUC__ */

static OneMultAddFunction *OneMultAdd[]={NULL,
					 UCHAR_onemultadd,
					 SCHAR_onemultadd,
					 SHORT_onemultadd,
					 INT_onemultadd,
					 LONG_onemultadd,
					 FLOAT_onemultadd,
					 DOUBLE_onemultadd,
					 CFLOAT_onemultadd,
					 CDOUBLE_onemultadd,
                                         NULL};


int pylab_convolve_2d (char  *in,        /* Input data Ns[0] x Ns[1] */
		       int   *instr,     /* Input strides */
		       char  *out,       /* Output data */
		       int   *outstr,    /* Ouput strides */
		       char  *hvals,     /* coefficients in filter */
		       int   *hstr,      /* coefficients strides */ 
		       int   *Nwin,      /* Size of kernel Nwin[0] x Nwin[1] */
		       int   *Ns,        /* Size of image Ns[0] x Ns[1] */
		       int   flag,       /* convolution parameters */
		       char  *fillvalue) /* fill value */
{
  int bounds_pad_flag = 0;
  int m, n, j, k, ind0, ind1;
  int Os[2];
  char *sum=NULL, *value=NULL;
  int new_m, new_n, ind0_memory;
  
  int boundary = flag & BOUNDARY_MASK;  /* flag can be fill, reflecting, circular */
  int outsize = flag & OUTSIZE_MASK;
  int convolve = flag & FLIP_MASK;
  int type_num = (flag & TYPE_MASK) >> TYPE_SHIFT;
  int type_size;
  OneMultAddFunction *mult_and_add;

  mult_and_add = OneMultAdd[type_num];
  if (mult_and_add == NULL) return -5;  /* Not available for this type */

  if (type_num < 0 || type_num > MAXTYPES) return -4;  /* Invalid type */
  type_size = elsize[type_num];

  if ((sum = calloc(type_size,2))==NULL) return -3; /* No memory */
  value = sum + type_size;

  if (outsize == FULL) {Os[0] = Ns[0]+Nwin[0]-1; Os[1] = Ns[0]+Nwin[1]-1;}
  else if (outsize == SAME) {Os[0] = Ns[0]; Os[1] = Ns[1];}
  else if (outsize == VALID) {Os[0] = Ns[0]-Nwin[0]+1; Os[1] = Ns[1]+Nwin[1]+1;}
  else return -1;  /* Invalid output flag */  
  
  if (boundary != PAD || boundary != REFLECT || boundary != CIRCULAR) 
    return -2;   /* Invalid boundary flag */

  for (m=0; m < Os[0]; m++) {
    /* Reposition index into input image based on requested output size */
    if (outsize == FULL) new_m = m-Nwin[0]+1;
    else if (outsize == SAME) new_m = m-((Nwin[0]-1) >> 1);
    else new_m = m; /* VALID */

    for (n=0; n < Os[1]; n++) {  /* loop over columns */
      memset(sum, 0, type_size); /* sum = 0.0; */

      if (outsize == FULL) new_n = n-Nwin[1]+1;
      else if (outsize == SAME) new_n = n-((Nwin[1]-1) >> 1);
      else new_n = n;

      /* Sum over kernel, if index into image is out of bounds
	 handle it according to boundary flag */
      for (j=0; j < Nwin[0]; j++) {
	if (convolve) 
	  ind0 = new_m-j;
	else
	  ind0 = new_m+j;

	bounds_pad_flag = 0;

	if (ind0 < 0) {
	  if (boundary == REFLECT) ind0 = -1-ind0;
	  else if (boundary == CIRCULAR) ind0 = Ns[0] - ind0; 
	  else bounds_pad_flag = 1;
	}
	else if (ind0 >= Ns[0]) {
	  if (boundary == REFLECT) ind0 = Ns[0]+Ns[0]-1-ind0;
	  else if (boundary == CIRCULAR) ind0 = ind0 - Ns[0]; 
	  else bounds_pad_flag = 1;
	}
	
	if (!bounds_pad_flag) ind0_memory = ind0*instr[0];

	for (k=0; k < Nwin[1]; k++) {
	  if (bounds_pad_flag) memcpy(value,fillvalue,type_size);
	  else {
	    if (convolve)
	      ind1 = new_n-k;
	    else
	      ind1 = new_n+k;

	    if (ind1 < 0) {
	      if (boundary == REFLECT) ind1 = -1-ind1;
	      else if (boundary == CIRCULAR) ind1 = Ns[1] - ind1;
	      else bounds_pad_flag = 1;
	    }
	    else if (ind1 >= Ns[1]) {
	      if (boundary == REFLECT) ind1 = Ns[1]+Ns[1]-1-ind1;
	      else if (boundary == CIRCULAR) ind1 = ind1 - Ns[1];
	      else bounds_pad_flag = 1;
	    }
	   
	    if (bounds_pad_flag) memcpy(value, fillvalue, type_size);
	    else memcpy(value, in+ind0_memory+ind1*instr[1], type_size);
	    bounds_pad_flag = 0;
	  }
	  mult_and_add(sum, hvals+j*hstr[0]+k*hstr[1], value);
	}
	memcpy(out+m*outstr[0]+n*outstr[1], sum, type_size);
      }
    }
  }
  free(sum);
  return 0;
}



