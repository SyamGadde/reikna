<%def name="prelude()">

%if thread_fast_math:
#define THREAD_FAST_MATH
%endif

%if api == 'cuda':
    #define CUDA
    // taken from pycuda._cluda
    #define LOCAL_BARRIER __syncthreads()

    #define WITHIN_KERNEL __device__
    #define KERNEL extern "C" __global__
    #define GLOBAL_MEM /* empty */
    #define LOCAL_MEM __shared__
    #define LOCAL_MEM_DYNAMIC extern __shared__
    #define LOCAL_MEM_ARG /* empty */
    #define INLINE __forceinline__

    <%
        dimnames = ['x', 'y', 'z']
    %>

    WITHIN_KERNEL int get_local_id(int dim)
    {
    %for n in range(3):
        if(dim == ${n}) return threadIdx.${dimnames[n]};
    %endfor
        return 0;
    }

    WITHIN_KERNEL int get_group_id(int dim)
    {
    %for n in range(3):
        if(dim == ${n}) return blockIdx.${dimnames[n]};
    %endfor
        return 0;
    }

    WITHIN_KERNEL int get_local_size(int dim)
    {
    %for n in range(3):
        if(dim == ${n}) return blockDim.${dimnames[n]};
    %endfor
        return 1;
    }

    WITHIN_KERNEL int get_num_groups(int dim)
    {
    %for n in range(3):
        if(dim == ${n}) return gridDim.${dimnames[n]};
    %endfor
        return 1;
    }

    WITHIN_KERNEL int get_global_size(int dim)
    {
        return get_num_groups(dim) * get_local_size(dim);
    }

    WITHIN_KERNEL int get_global_id(int dim)
    {
        return get_local_id(dim) + get_group_id(dim) * get_local_size(dim);
    }

%elif api == 'ocl':
    // taken from pyopencl._cluda
    #define LOCAL_BARRIER barrier(CLK_LOCAL_MEM_FENCE)

    // 'static' helps to avoid the "no previous prototype for function" warning
    #if __OPENCL_VERSION__ >= 120
    #define WITHIN_KERNEL static
    #else
    #define WITHIN_KERNEL
    #endif

    #define KERNEL __kernel
    #define GLOBAL_MEM __global
    #define LOCAL_MEM __local
    #define LOCAL_MEM_DYNAMIC __local
    #define LOCAL_MEM_ARG __local
    #define INLINE inline

    #if defined(cl_khr_fp64)
    #pragma OPENCL EXTENSION cl_khr_fp64: enable
    #elif defined(cl_amd_fp64)
    #pragma OPENCL EXTENSION cl_amd_fp64: enable
    #endif

%endif

%if api == 'cuda':
    #define COMPLEX_CTR(T) make_##T
%elif api == 'ocl':
    #define COMPLEX_CTR(T) (T)
%endif

## These operators are supported by OpenCL
%if api == 'cuda':
%for tp in ('float2', 'double2'):
    WITHIN_KERNEL ${tp} operator+(${tp} a, ${tp} b)
    {
        return COMPLEX_CTR(${tp})(a.x + b.x, a.y + b.y);
    }
    WITHIN_KERNEL ${tp} operator-(${tp} a, ${tp} b)
    {
        return COMPLEX_CTR(${tp})(a.x - b.x, a.y - b.y);
    }
    WITHIN_KERNEL ${tp} operator+(${tp} a) { return a; }
    WITHIN_KERNEL ${tp} operator-(${tp} a) { return COMPLEX_CTR(${tp})(-a.x, -a.y); }
%endfor
%endif

</%def>