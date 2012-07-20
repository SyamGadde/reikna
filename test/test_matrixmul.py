import numpy
import pytest

from helpers import *

from tigger.matrixmul import MatrixMul
from tigger.dummy import Dummy
from tigger.core.transformation import Transformation
import tigger.cluda.dtypes as dtypes

@pytest.mark.parametrize("complex1", [False, True], ids=['real', 'complex'])
@pytest.mark.parametrize("complex2", [False, True], ids=['real', 'complex'])
def test_errors(ctx_and_double, complex1, complex2):

    ctx, double = ctx_and_double

    s1 = (100, 200)
    s2 = (200, 100)

    dtype = numpy.float64 if double else numpy.float32
    dtype1 = dtypes.complex_for(dtype) if complex1 else dtype
    dtype2 = dtypes.complex_for(dtype) if complex2 else dtype
    res_dtype = numpy.result_type(dtype1, dtype2)

    a = getTestArray(s1, dtype1)
    b = getTestArray(s2, dtype2)

    a_dev = ctx.to_device(a)
    b_dev = ctx.to_device(b)
    res_dev = ctx.allocate((s1[0], s2[1]), dtype=res_dtype)
    dot = MatrixMul(ctx).prepare_for(res_dev, a_dev, b_dev)
    dot(res_dev, a_dev, b_dev)

    assert diff(ctx.from_device(res_dev), numpy.dot(a, b)) < 1e-6

def test_preprocessing(ctx_and_double):

    ctx, double = ctx_and_double

    coeff = numpy.float32(2)
    B_param = numpy.float32(3)
    N = 1024

    def mock_dummy(a, b):
        res = a + (a * B_param + b) * coeff
        return res / 2, res / 2

    a = Transformation(load=1, store=1,
        code="${store.s1}(${load.l1});")

    b = Transformation(load=2, store=1, parameters=1,
        derive_s_from_lp=lambda l1, l2, p1: [l1],
        derive_lp_from_s=lambda s1: ([s1, s1], [numpy.float32]),
        derive_l_from_sp=lambda s1, p1: [s1, s1],
        derive_sp_from_l=lambda l1, l2: ([l1], [numpy.float32]),
        code="""
            ${ctype.s1} t = ${func.mul(dtype.s1, dtype.l1)}(
                ${func.cast(dtype.s1, dtype.p1)}(${param.p1}), ${load.l1});
            ${store.s1}(t + ${load.l2});
        """)

    c = Transformation(load=1, store=2,
        code="""
            ${ctype.s1} t = ${func.mul(dtype.l1, numpy.float32)}(${load.l1}, 0.5);
            ${store.s1}(t);
            ${store.s2}(t);
        """)

    d = Dummy(ctx)
    assert d.signature_str() == "(array) C, (array) A, (array) B, (scalar) coeff"

    d.connect(a, 'A', ['A_prime']);
    d.connect(b, 'B', ['A_prime', 'B_prime'], ['B_param'])
    d.connect(a, 'B_prime', ['B_new_prime'])
    d.connect(c, 'C', ['C_half1', 'C_half2'])
    d.connect(a, 'C_half1', ['C_new_half1'])

    d.prepare(arr_dtype=numpy.float32, size=N)
    assert d.signature_str() == "(array, float32) C_new_half1, (array, float32) C_half2, " \
        "(array, float32) A_prime, (array, float32) B_new_prime, " \
        "(scalar, <type 'numpy.float32'>) coeff, (scalar, <type 'numpy.float32'>) B_param"

    A_prime = getTestArray(N, numpy.complex64)
    B_new_prime = getTestArray(N, numpy.complex64)
    gpu_A_prime = ctx.to_device(A_prime)
    gpu_B_new_prime = ctx.to_device(B_new_prime)
    gpu_C_new_half1 = ctx.allocate(N, numpy.complex64)
    gpu_C_half2 = ctx.allocate(N, numpy.complex64)
    d.prepare_for(gpu_C_new_half1, gpu_C_half2,
        gpu_A_prime, gpu_B_new_prime, numpy.float32(coeff), numpy.int32(B_param))
    assert d.signature_str() == "(array, complex64, (1024,)) C_new_half1, " \
        "(array, complex64, (1024,)) C_half2, (array, complex64, (1024,)) A_prime, " \
        "(array, complex64, (1024,)) B_new_prime, (scalar, <type 'numpy.float32'>) coeff, " \
        "(scalar, <type 'numpy.float32'>) B_param"

    d(gpu_C_new_half1, gpu_C_half2, gpu_A_prime, gpu_B_new_prime, coeff, B_param)
    C_new_half1, C_half2 = mock_dummy(A_prime, B_new_prime)

    assert diff(ctx.from_device(gpu_C_new_half1), C_new_half1) < 1e-6
    assert diff(ctx.from_device(gpu_C_half2), C_half2) < 1e-6