#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
import pytest
import sympy

import cirq
import cirq.testing as ct
from cirq import Circuit
from cirq.circuits.qasm_output import QasmUGate
from cirq.contrib.qasm_import import QasmException
from cirq.contrib.qasm_import._parser import QasmParser


def test_format_header_circuit():
    parser = QasmParser()

    parsed_qasm = parser.parse("OPENQASM 2.0;")

    assert parsed_qasm.supportedFormat
    assert not parsed_qasm.qelib1Include
    ct.assert_same_circuits(parsed_qasm.circuit, Circuit())


def test_unsupported_format():
    qasm = "OPENQASM 2.1;"
    parser = QasmParser()

    with pytest.raises(QasmException,
                       match="Unsupported OpenQASM version: 2.1, "
                       "only 2.0 is supported currently by Cirq"):
        parser.parse(qasm)


def test_format_header_with_quelibinc_circuit():
    qasm = """OPENQASM 2.0;
include "qelib1.inc";
"""
    parser = QasmParser()

    parsed_qasm = parser.parse(qasm)

    assert parsed_qasm.supportedFormat
    assert parsed_qasm.qelib1Include
    ct.assert_same_circuits(parsed_qasm.circuit, Circuit())


@pytest.mark.parametrize('qasm', [
    "include \"qelib1.inc\";",
    "",
    "qreg q[3];",
])
def test_error_not_starting_with_format(qasm: str):
    parser = QasmParser()

    with pytest.raises(QasmException,
                       match="Missing 'OPENQASM 2.0;' statement"):
        parser.parse(qasm)


def test_comments():
    parser = QasmParser()

    parsed_qasm = parser.parse("""
    //this is the format 
    OPENQASM 2.0;
    // this is some other comment
    include "qelib1.inc";
    // and something at the end of the file
    // multiline 
    """)

    assert parsed_qasm.supportedFormat
    assert parsed_qasm.qelib1Include
    ct.assert_same_circuits(parsed_qasm.circuit, Circuit())


def test_multiple_qreg_declaration():
    qasm = """OPENQASM 2.0;
     include "qelib1.inc";
     qreg a_quantum_register [ 1337 ];
     qreg q[42];
"""
    parser = QasmParser()

    parsed_qasm = parser.parse(qasm)

    assert parsed_qasm.supportedFormat
    assert parsed_qasm.qelib1Include
    ct.assert_same_circuits(parsed_qasm.circuit, Circuit())
    assert parsed_qasm.qregs == {'a_quantum_register': 1337, 'q': 42}


@pytest.mark.parametrize('qasm', [
    """OPENQASM 2.0;
           qreg q[2];
           creg q[3];
               """,
    """OPENQASM 2.0;
           creg q[2];
           qreg q[3];
               """,
])
def test_already_defined_error(qasm: str):
    parser = QasmParser()

    with pytest.raises(QasmException, match=r"q.*already defined.* line 3"):
        parser.parse(qasm)


@pytest.mark.parametrize('qasm', [
    """OPENQASM 2.0;
           qreg q[0];
               """,
    """OPENQASM 2.0;
           creg q[0];
               """,
])
def test_zero_length_register(qasm: str):
    parser = QasmParser()

    with pytest.raises(QasmException,
                       match="Illegal, zero-length register 'q' at line 2"):
        parser.parse(qasm)


def test_unexpected_end_of_file():
    qasm = """OPENQASM 2.0;
              include "qelib1.inc";
              creg
           """
    parser = QasmParser()

    with pytest.raises(QasmException, match="Unexpected end of file"):
        parser.parse(qasm)


def test_multiple_creg_declaration():
    qasm = """OPENQASM 2.0;
     include "qelib1.inc";
     creg a_classical_register [1337];
     qreg a_quantum_register [1337];
     creg c[42];
"""
    parser = QasmParser()

    parsed_qasm = parser.parse(qasm)

    assert parsed_qasm.supportedFormat
    assert parsed_qasm.qelib1Include
    ct.assert_same_circuits(parsed_qasm.circuit, Circuit())
    assert parsed_qasm.qregs == {'a_quantum_register': 1337}
    assert parsed_qasm.cregs == {'a_classical_register': 1337, 'c': 42}


def test_syntax_error():
    qasm = """OPENQASM 2.0;
         qreg q[2] bla;
         foobar q[0];
    """
    parser = QasmParser()

    with pytest.raises(QasmException, match=r"""Syntax error: 'bla'.*"""):
        parser.parse(qasm)


def test_CX_gate():
    qasm = """OPENQASM 2.0;
     qreg q1[2];
     qreg q2[2];
     CX q1[0], q1[1];
     CX q1, q2[0];
     CX q2, q1;      
"""
    parser = QasmParser()

    q1_0 = cirq.NamedQubit('q1_0')
    q1_1 = cirq.NamedQubit('q1_1')
    q2_0 = cirq.NamedQubit('q2_0')
    q2_1 = cirq.NamedQubit('q2_1')

    expected_circuit = Circuit()
    # CX q1[0], q1[1];
    expected_circuit.append(cirq.CNOT(q1_0, q1_1))
    # CX q1, q2[0];
    expected_circuit.append(cirq.CNOT(q1_0, q2_0))
    expected_circuit.append(cirq.CNOT(q1_1, q2_0))
    # CX q2, q1;
    expected_circuit.append(cirq.CNOT(q2_0, q1_0))
    expected_circuit.append(cirq.CNOT(q2_1, q1_1))

    parsed_qasm = parser.parse(qasm)

    assert parsed_qasm.supportedFormat
    assert not parsed_qasm.qelib1Include

    ct.assert_same_circuits(parsed_qasm.circuit, expected_circuit)
    assert parsed_qasm.qregs == {'q1': 2, 'q2': 2}


def test_CX_gate_not_enough_args():
    qasm = """OPENQASM 2.0;
     qreg q[2];
     CX q[0];
"""
    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=(r"CX only takes 2 arg\(s\) "
                              r"\(qubits and/or registers\)"
                              r", got: 1, at line 3")):
        parser.parse(qasm)


def test_cx_gate_mismatched_registers():
    qasm = """OPENQASM 2.0;
     qreg q1[2];
     qreg q2[3];
     CX q1, q2;
"""
    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=r"Non matching quantum registers of "
                       r"length \[2 3\] at line 4"):
        parser.parse(qasm)


def test_cx_gate_bounds():
    qasm = """OPENQASM 2.0;
     qreg q1[2];
     qreg q2[3];
     CX q1[4], q2[0];
"""
    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=r"Out of bounds qubit index 4"
                       r" on register q1 of size 2 at line 4"):
        parser.parse(qasm)


def test_cx_gate_arg_overlap():
    qasm = """OPENQASM 2.0;
     qreg q1[2];
     qreg q2[3];
     CX q1[1], q1[1];
"""
    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=r"Overlapping qubits in arguments"
                       r" at line 4"):
        parser.parse(qasm)


def test_u_gate():
    qasm = """
     OPENQASM 2.0;
     qreg q[2];
     U(pi, 2.3, 3) q[0];
     U(+3.14, -pi, (8)) q;
"""
    parser = QasmParser()

    q0 = cirq.NamedQubit('q_0')
    q1 = cirq.NamedQubit('q_1')

    expected_circuit = Circuit()
    expected_circuit.append(QasmUGate(1.0, 2.3 / np.pi, 3 / np.pi)(q0))

    expected_circuit.append(
        cirq.Moment([
            QasmUGate(3.14 / np.pi, -1.0, 8 / np.pi)(q0),
            QasmUGate(3.14 / np.pi, -1.0, 8 / np.pi)(q1)
        ]))

    parsed_qasm = parser.parse(qasm)

    assert parsed_qasm.supportedFormat
    assert not parsed_qasm.qelib1Include

    ct.assert_same_circuits(parsed_qasm.circuit, expected_circuit)
    assert parsed_qasm.qregs == {'q': 2}


def test_u3_angles():
    qasm = """
    OPENQASM 2.0;
    qreg q[1];
    U(pi/2,0,pi) q[0];
    """

    c = QasmParser().parse(qasm).circuit
    cirq.testing.assert_allclose_up_to_global_phase(cirq.unitary(c),
                                                    cirq.unitary(cirq.H),
                                                    atol=1e-7)


@pytest.mark.parametrize(
    'expr',
    [
        '.333 + 4',
        '1.0 * 2',
        '0.1 ^ pi',
        '0.1 / pi',
        '2.0e-05 ^ (1/2)',
        '1.2E+05 * (3 + 2)',
        '123123.2132312 * cos(pi)',
        '123123.2132312 * sin(2 * pi)',
        '3 - 4 * 2',  # precedence of *
        '3 * 4 + 2',  # precedence of *
        '3 * 4 ^ 2',  # precedence of ^
        '3 - 4 ^ 2',  # precedence of ^
        '3^2^(-2)',  # right associativity of ^
        '(-1) * pi',
        '(+1) * pi',
        '-3 * 5 + 2',
        '(+4 * (-3) ^ 5 - 2)',
        'tan(123123.2132312)',
        'ln(pi)',
        'exp(2*pi)',
        'sqrt(4)',
        'acos(1)',
        'atan(0.2)',
    ])
def test_expressions(expr: str):
    qasm = """OPENQASM 2.0;
     qreg q[1];
     U({}, 2 * pi, pi / 2.0) q[0];
""".format(expr)

    parser = QasmParser()

    q0 = cirq.NamedQubit('q_0')

    expected_circuit = Circuit()
    expected_circuit.append(
        QasmUGate(float(sympy.sympify(expr)) / np.pi, 2.0, 1 / 2.0)(q0))

    parsed_qasm = parser.parse(qasm)

    assert parsed_qasm.supportedFormat
    assert not parsed_qasm.qelib1Include

    ct.assert_allclose_up_to_global_phase(cirq.unitary(parsed_qasm.circuit),
                                          cirq.unitary(expected_circuit),
                                          atol=1e-10)
    assert parsed_qasm.qregs == {'q': 1}


def test_unknown_function():
    qasm = """OPENQASM 2.0;
     qreg q[1];
     U(nonexistent(3), 2 * pi, pi / 3.0) q[0];
"""
    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=r"Function not recognized:"
                       r" 'nonexistent' at line 3"):
        parser.parse(qasm)


def test_u_gate_zero_params_error():
    qasm = """OPENQASM 2.0;
     qreg q[2];     
     U() q[1];"""

    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=r"U takes 3 parameter\(s\).*got.*0.*line 3"):
        parser.parse(qasm)


def test_u_gate_too_much_params_error():
    qasm = """OPENQASM 2.0;
     qreg q[2];     
     U(pi, pi, pi, pi) q[1];"""

    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=r"U takes 3 parameter\(s\).*got.*4.*line 3"):
        parser.parse(qasm)


def test_unknown_basic_gate():
    qasm = """OPENQASM 2.0;
         qreg q[2];
         foobar q[0];
    """
    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=r"""Unknown gate "foobar".* line 3.*forgot.*\?"""):
        parser.parse(qasm)


def test_undefined_register_from_qubit_arg():
    qasm = """OPENQASM 2.0;
            qreg q[2];
            CX q[0], q2[1];
       """
    parser = QasmParser()

    with pytest.raises(QasmException, match=r"""Undefined.*register.*q2.*"""):
        parser.parse(qasm)


def test_undefined_register_from_register_arg():
    qasm = """OPENQASM 2.0;
            qreg q[2];
            qreg q2[2];
            CX q1, q2;
       """
    parser = QasmParser()

    with pytest.raises(QasmException, match=r"""Undefined.*register.*q.*"""):
        parser.parse(qasm)


def test_measure_individual_bits():
    qasm = """
         OPENQASM 2.0;   
         include "qelib1.inc";       
         qreg q1[2];
         creg c1[2];                        
         measure q1[0] -> c1[0];
         measure q1[1] -> c1[1];
    """
    parser = QasmParser()

    q1_0 = cirq.NamedQubit('q1_0')
    q1_1 = cirq.NamedQubit('q1_1')

    expected_circuit = Circuit()

    expected_circuit.append(
        cirq.MeasurementGate(num_qubits=1, key='c1_1').on(q1_1))
    expected_circuit.append(
        cirq.MeasurementGate(num_qubits=1, key='c1_0').on(q1_0))

    parsed_qasm = parser.parse(qasm)

    assert parsed_qasm.supportedFormat
    assert parsed_qasm.qelib1Include

    ct.assert_same_circuits(parsed_qasm.circuit, expected_circuit)
    assert parsed_qasm.qregs == {'q1': 2}
    assert parsed_qasm.cregs == {'c1': 2}


def test_measure_registers():
    qasm = """
         OPENQASM 2.0;   
         include "qelib1.inc";       
         qreg q1[3];
         creg c1[3];                        
         measure q1 -> c1;       
    """
    parser = QasmParser()

    q1_0 = cirq.NamedQubit('q1_0')
    q1_1 = cirq.NamedQubit('q1_1')
    q1_2 = cirq.NamedQubit('q1_2')

    expected_circuit = Circuit()

    expected_circuit.append(
        cirq.MeasurementGate(num_qubits=1, key='c1_0').on(q1_0))
    expected_circuit.append(
        cirq.MeasurementGate(num_qubits=1, key='c1_1').on(q1_1))
    expected_circuit.append(
        cirq.MeasurementGate(num_qubits=1, key='c1_2').on(q1_2))

    parsed_qasm = parser.parse(qasm)

    assert parsed_qasm.supportedFormat
    assert parsed_qasm.qelib1Include

    ct.assert_same_circuits(parsed_qasm.circuit, expected_circuit)
    assert parsed_qasm.qregs == {'q1': 3}
    assert parsed_qasm.cregs == {'c1': 3}


def test_measure_mismatched_register_size():
    qasm = """
         OPENQASM 2.0;   
         include "qelib1.inc";       
         qreg q1[2];
         creg c1[3];                        
         measure q1 -> c1;       
    """

    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=r""".*mismatched register sizes 2 -> 3.*line 6"""):
        parser.parse(qasm)


def test_measure_to_quantum_register():
    qasm = """OPENQASM 2.0;
         include "qelib1.inc";       
         qreg q1[3];
         qreg q2[3];
         creg c1[3];                        
         measure q2 -> q1;       
    """

    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=r"""Undefined classical register.*q1.*line 6"""):
        parser.parse(qasm)


def test_measure_undefined_classical_bit():
    qasm = """OPENQASM 2.0;
         include "qelib1.inc";       
         qreg q1[3];    
         creg c1[3];                        
         measure q1[1] -> c2[1];       
    """

    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=r"""Undefined classical register.*c2.*line 5"""):
        parser.parse(qasm)


def test_measure_from_classical_register():
    qasm = """OPENQASM 2.0;
         include "qelib1.inc";       
         qreg q1[2];
         creg c1[3];                        
         creg c2[3];                        
         measure c1 -> c2;       
    """

    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=r"""Undefined quantum register.*c1.*line 6"""):
        parser.parse(qasm)


def test_measurement_bounds():
    qasm = """OPENQASM 2.0;
     qreg q1[3];
     creg c1[3];                        
     measure q1[0] -> c1[4];  
"""
    parser = QasmParser()

    with pytest.raises(QasmException,
                       match=r"Out of bounds bit index 4"
                       r" on classical register c1 of size 3 at line 4"):
        parser.parse(qasm)
