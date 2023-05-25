#!/usr/bin/env python3

"""Helper functions used by the code generator"""

from regalloc import *

REG_FP = 11
REG_SCRATCH = 12
REG_SP = 13
REG_LR = 14
REG_PC = 15

REGS_CALLEESAVE = [4, 5, 6, 7, 8, 9, 10]
REGS_CALLERSAVE = [0, 1, 2, 3]

# each time a call gets made, the caller saved and the callee saved registers
# gets pushed on the stack, + the current frame pointer and return pointer
CALL_OFFSET = (len(REGS_CALLEESAVE) + len(REGS_CALLERSAVE) + 2) * 4


def get_register_string(regid):
    if regid == REG_LR:
        return 'lr'
    if regid == REG_SP:
        return 'sp'
    return 'r' + repr(regid)


def save_regs(reglist):
    if len(reglist) == 0:
        return ''
    res = '\tpush {'
    for i in range(0, len(reglist)):
        if i > 0:
            res += ', '
        res += get_register_string(reglist[i])
    res += '}\n'
    return res


def restore_regs(reglist):
    if len(reglist) == 0:
        return ''
    res = '\tpop {'
    for i in range(0, len(reglist)):
        if i > 0:
            res += ', '
        res += get_register_string(reglist[i])
    res += '}\n'
    return res


def comment(cont):
    return '@ ' + cont + '\n'


def codegen_append(vec, code):
    if type(code) is list:
        return [vec[0] + code[0], vec[1] + code[1]]
    return [vec[0] + code, vec[1]]


# If a variable needs a static link, add the correct offset to the frame pointer, put
# the result in the scratch register and use that to reference the variable
#
# This workaround of using the scratch register is needed because it's impossible to
# add directly to the frame pointer
def check_if_variable_needs_static_link(node, symbol):
    real_offset = static_link_analysis(node, symbol)

    if real_offset > 0:
        return '\tadd ' + get_register_string(REG_SCRATCH) + ', ' + get_register_string(REG_FP) + ', #' + str(real_offset) + '\n'


# If a nested function uses a variable of its (grand)parent, its offset will be wrong
# because it will be in reference to the frame pointer of the parent; this analysis finds
# the real offset and adds instructions to correct it
def static_link_analysis(node, symbol):
    function_definition = node.get_function()

    if symbol.allocinfo.symname.startswith("_l_") and symbol.fname != function_definition.symbol.name:
        return get_static_link_offset(function_definition, symbol.fname, 0)

    return 0


# Recursively keep adding the offset (saved registers + local variables of the caller) of
# each function until the specified function is found; this offset + the current frame
# pointer will point to the frame pointer of the parent
def get_static_link_offset(node, function_name, offset):
    function_definition = node.get_function()

    if function_definition == 'global':
        raise RuntimeError("Main function does not have local variables")

    offset += CALL_OFFSET
    offset += function_definition.body.stackroom

    if function_definition.symbol.name == function_name:
        return offset

    return get_static_link_offset(function_definition, function_name, offset)


def enter_function_body(self, block):
    self.curfun = block
    self.spillvarloc = dict()
    self.spillvarloctop = -block.stackroom


def gen_spill_load_if_necessary(self, var):
    self.dematerialize_spilled_var_if_necessary(var)
    if not self.materialize_spilled_var_if_necessary(var):
        # not a spilled variable
        return ''
    offs = self.spillvarloctop - self.vartospillframeoffset[var] - 4
    rd = self.get_register_for_variable(var)
    res = '\tldr ' + rd + ', [' + get_register_string(REG_FP) + ', #' + repr(offs) + ']'
    res += '\t' + comment('<<- fill')
    return res


def get_register_for_variable(self, var):
    self.materialize_spilled_var_if_necessary(var)
    res = get_register_string(self.vartoreg[var])
    return res


def gen_spill_store_if_necessary(self, var):
    if not self.materialize_spilled_var_if_necessary(var):
        # not a spilled variable
        return ''
    offs = self.spillvarloctop - self.vartospillframeoffset[var] - 4
    rd = self.get_register_for_variable(var)
    res = '\tstr ' + rd + ', [' + get_register_string(REG_FP) + ', #' + repr(offs) + ']'
    res += '\t' + comment('<<- spill')
    self.dematerialize_spilled_var_if_necessary(var)
    return res


RegisterAllocation.enter_function_body = enter_function_body
RegisterAllocation.gen_spill_load_if_necessary = gen_spill_load_if_necessary
RegisterAllocation.get_register_for_variable = get_register_for_variable
RegisterAllocation.gen_spill_store_if_necessary = gen_spill_store_if_necessary
