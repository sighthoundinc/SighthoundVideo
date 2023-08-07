#!/usr/bin/env python

#*****************************************************************************
#
# Statistics.py
#
#
#
#*****************************************************************************
#
#
# Copyright 2013-2022 Arden.ai, Inc.
#
# Licensed under the GNU GPLv3 license found at
# https://www.gnu.org/licenses/gpl-3.0.txt
#
# Alternative licensing available from Arden.ai, Inc.
# by emailing opensource@ardenai.com
#
# This file is part of the Arden AI project which can be found at
# https://github.com/ardenaiinc/ArdenAI
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; using version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02111, USA.
#
#
#*****************************************************************************

from math import exp, fabs, sqrt, tan


# Constants used to implement computePValueForStdNormal()
# and computeZValueForStdNormal()
_kSqrtTwo   = 1.414213562373095

# Constants used to implement _erfc() and _erfcinv() function.
_kSqrtPi      = 1.772453850905516
_kBigNumber   = 1e10
_kXLo         = 0.0
_kDeltaX      = 0.01
_kPLo         = 1.0e-3
_kDeltaP      = 5.0e-4

_kErfcArgs    = \
   [0.0000000e+00, 1.0000000e-02, 2.0000000e-02, 3.0000000e-02, 4.0000000e-02,
    5.0000000e-02, 6.0000000e-02, 7.0000000e-02, 8.0000000e-02, 9.0000000e-02,
    1.0000000e-01, 1.1000000e-01, 1.2000000e-01, 1.3000000e-01, 1.4000000e-01,
    1.5000000e-01, 1.6000000e-01, 1.7000000e-01, 1.8000000e-01, 1.9000000e-01,
    2.0000000e-01, 2.1000000e-01, 2.2000000e-01, 2.3000000e-01, 2.4000000e-01,
    2.5000000e-01, 2.6000000e-01, 2.7000000e-01, 2.8000000e-01, 2.9000000e-01,
    3.0000000e-01, 3.1000000e-01, 3.2000000e-01, 3.3000000e-01, 3.4000000e-01,
    3.5000000e-01, 3.6000000e-01, 3.7000000e-01, 3.8000000e-01, 3.9000000e-01,
    4.0000000e-01, 4.1000000e-01, 4.2000000e-01, 4.3000000e-01, 4.4000000e-01,
    4.5000000e-01, 4.6000000e-01, 4.7000000e-01, 4.8000000e-01, 4.9000000e-01,
    5.0000000e-01, 5.1000000e-01, 5.2000000e-01, 5.3000000e-01, 5.4000000e-01,
    5.5000000e-01, 5.6000000e-01, 5.7000000e-01, 5.8000000e-01, 5.9000000e-01,
    6.0000000e-01, 6.1000000e-01, 6.2000000e-01, 6.3000000e-01, 6.4000000e-01,
    6.5000000e-01, 6.6000000e-01, 6.7000000e-01, 6.8000000e-01, 6.9000000e-01,
    7.0000000e-01, 7.1000000e-01, 7.2000000e-01, 7.3000000e-01, 7.4000000e-01,
    7.5000000e-01, 7.6000000e-01, 7.7000000e-01, 7.8000000e-01, 7.9000000e-01,
    8.0000000e-01, 8.1000000e-01, 8.2000000e-01, 8.3000000e-01, 8.4000000e-01,
    8.5000000e-01, 8.6000000e-01, 8.7000000e-01, 8.8000000e-01, 8.9000000e-01,
    9.0000000e-01, 9.1000000e-01, 9.2000000e-01, 9.3000000e-01, 9.4000000e-01,
    9.5000000e-01, 9.6000000e-01, 9.7000000e-01, 9.8000000e-01, 9.9000000e-01,
    1.0000000e+00, 1.0100000e+00, 1.0200000e+00, 1.0300000e+00, 1.0400000e+00,
    1.0500000e+00, 1.0600000e+00, 1.0700000e+00, 1.0800000e+00, 1.0900000e+00,
    1.1000000e+00, 1.1100000e+00, 1.1200000e+00, 1.1300000e+00, 1.1400000e+00,
    1.1500000e+00, 1.1600000e+00, 1.1700000e+00, 1.1800000e+00, 1.1900000e+00,
    1.2000000e+00, 1.2100000e+00, 1.2200000e+00, 1.2300000e+00, 1.2400000e+00,
    1.2500000e+00, 1.2600000e+00, 1.2700000e+00, 1.2800000e+00, 1.2900000e+00,
    1.3000000e+00, 1.3100000e+00, 1.3200000e+00, 1.3300000e+00, 1.3400000e+00,
    1.3500000e+00, 1.3600000e+00, 1.3700000e+00, 1.3800000e+00, 1.3900000e+00,
    1.4000000e+00, 1.4100000e+00, 1.4200000e+00, 1.4300000e+00, 1.4400000e+00,
    1.4500000e+00, 1.4600000e+00, 1.4700000e+00, 1.4800000e+00, 1.4900000e+00,
    1.5000000e+00, 1.5100000e+00, 1.5200000e+00, 1.5300000e+00, 1.5400000e+00,
    1.5500000e+00, 1.5600000e+00, 1.5700000e+00, 1.5800000e+00, 1.5900000e+00,
    1.6000000e+00, 1.6100000e+00, 1.6200000e+00, 1.6300000e+00, 1.6400000e+00,
    1.6500000e+00, 1.6600000e+00, 1.6700000e+00, 1.6800000e+00, 1.6900000e+00,
    1.7000000e+00, 1.7100000e+00, 1.7200000e+00, 1.7300000e+00, 1.7400000e+00,
    1.7500000e+00, 1.7600000e+00, 1.7700000e+00, 1.7800000e+00, 1.7900000e+00,
    1.8000000e+00, 1.8100000e+00, 1.8200000e+00, 1.8300000e+00, 1.8400000e+00,
    1.8500000e+00, 1.8600000e+00, 1.8700000e+00, 1.8800000e+00, 1.8900000e+00,
    1.9000000e+00, 1.9100000e+00, 1.9200000e+00, 1.9300000e+00, 1.9400000e+00,
    1.9500000e+00, 1.9600000e+00, 1.9700000e+00, 1.9800000e+00, 1.9900000e+00,
    2.0000000e+00, 2.0100000e+00, 2.0200000e+00, 2.0300000e+00, 2.0400000e+00,
    2.0500000e+00, 2.0600000e+00, 2.0700000e+00, 2.0800000e+00, 2.0900000e+00,
    2.1000000e+00, 2.1100000e+00, 2.1200000e+00, 2.1300000e+00, 2.1400000e+00,
    2.1500000e+00, 2.1600000e+00, 2.1700000e+00, 2.1800000e+00, 2.1900000e+00,
    2.2000000e+00, 2.2100000e+00, 2.2200000e+00, 2.2300000e+00, 2.2400000e+00,
    2.2500000e+00, 2.2600000e+00, 2.2700000e+00, 2.2800000e+00, 2.2900000e+00,
    2.3000000e+00, 2.3100000e+00, 2.3200000e+00, 2.3300000e+00, 2.3400000e+00,
    2.3500000e+00, 2.3600000e+00, 2.3700000e+00, 2.3800000e+00, 2.3900000e+00,
    2.4000000e+00, 2.4100000e+00, 2.4200000e+00, 2.4300000e+00, 2.4400000e+00,
    2.4500000e+00, 2.4600000e+00, 2.4700000e+00, 2.4800000e+00, 2.4900000e+00,
    2.5000000e+00, 2.5100000e+00, 2.5200000e+00, 2.5300000e+00, 2.5400000e+00,
    2.5500000e+00, 2.5600000e+00, 2.5700000e+00, 2.5800000e+00, 2.5900000e+00,
    2.6000000e+00, 2.6100000e+00, 2.6200000e+00, 2.6300000e+00, 2.6400000e+00,
    2.6500000e+00, 2.6600000e+00, 2.6700000e+00, 2.6800000e+00, 2.6900000e+00,
    2.7000000e+00, 2.7100000e+00, 2.7200000e+00, 2.7300000e+00, 2.7400000e+00,
    2.7500000e+00, 2.7600000e+00, 2.7700000e+00, 2.7800000e+00, 2.7900000e+00,
    2.8000000e+00, 2.8100000e+00, 2.8200000e+00, 2.8300000e+00, 2.8400000e+00,
    2.8500000e+00, 2.8600000e+00, 2.8700000e+00, 2.8800000e+00, 2.8900000e+00,
    2.9000000e+00, 2.9100000e+00, 2.9200000e+00, 2.9300000e+00, 2.9400000e+00,
    2.9500000e+00, 2.9600000e+00, 2.9700000e+00, 2.9800000e+00, 2.9900000e+00,
    3.0000000e+00, 3.0100000e+00, 3.0200000e+00, 3.0300000e+00, 3.0400000e+00,
    3.0500000e+00, 3.0600000e+00, 3.0700000e+00, 3.0800000e+00, 3.0900000e+00,
    3.1000000e+00, 3.1100000e+00, 3.1200000e+00, 3.1300000e+00, 3.1400000e+00,
    3.1500000e+00, 3.1600000e+00, 3.1700000e+00, 3.1800000e+00, 3.1900000e+00,
    3.2000000e+00, 3.2100000e+00, 3.2200000e+00, 3.2300000e+00, 3.2400000e+00,
    3.2500000e+00, 3.2600000e+00, 3.2700000e+00, 3.2800000e+00, 3.2900000e+00,
    3.3000000e+00, 3.3100000e+00, 3.3200000e+00, 3.3300000e+00, 3.3400000e+00,
    3.3500000e+00, 3.3600000e+00, 3.3700000e+00, 3.3800000e+00, 3.3900000e+00,
    3.4000000e+00, 3.4100000e+00, 3.4200000e+00, 3.4300000e+00, 3.4400000e+00,
    3.4500000e+00, 3.4600000e+00, 3.4700000e+00, 3.4800000e+00, 3.4900000e+00,
    3.5000000e+00, 3.5100000e+00, 3.5200000e+00, 3.5300000e+00, 3.5400000e+00,
    3.5500000e+00, 3.5600000e+00, 3.5700000e+00, 3.5800000e+00, 3.5900000e+00,
    3.6000000e+00, 3.6100000e+00, 3.6200000e+00, 3.6300000e+00, 3.6400000e+00,
    3.6500000e+00, 3.6600000e+00, 3.6700000e+00, 3.6800000e+00, 3.6900000e+00,
    3.7000000e+00, 3.7100000e+00, 3.7200000e+00, 3.7300000e+00, 3.7400000e+00,
    3.7500000e+00, 3.7600000e+00, 3.7700000e+00, 3.7800000e+00, 3.7900000e+00,
    3.8000000e+00, 3.8100000e+00, 3.8200000e+00, 3.8300000e+00, 3.8400000e+00,
    3.8500000e+00, 3.8600000e+00, 3.8700000e+00, 3.8800000e+00, 3.8900000e+00,
    3.9000000e+00, 3.9100000e+00, 3.9200000e+00, 3.9300000e+00, 3.9400000e+00,
    3.9500000e+00, 3.9600000e+00, 3.9700000e+00, 3.9800000e+00, 3.9900000e+00,
    4.0000000e+00, ]

_kErfcVals = \
   [1.0000000e+00, 9.8871658e-01, 9.7743543e-01, 9.6615878e-01, 9.5488889e-01,
    9.4362802e-01, 9.3237841e-01, 9.2114228e-01, 9.0992187e-01, 8.9871941e-01,
    8.8753708e-01, 8.7637710e-01, 8.6524165e-01, 8.5413289e-01, 8.4305297e-01,
    8.3200403e-01, 8.2098819e-01, 8.1000754e-01, 7.9906416e-01, 7.8816011e-01,
    7.7729741e-01, 7.6647808e-01, 7.5570409e-01, 7.4497740e-01, 7.3429994e-01,
    7.2367361e-01, 7.1310028e-01, 7.0258178e-01, 6.9211993e-01, 6.8171650e-01,
    6.7137324e-01, 6.6109185e-01, 6.5087401e-01, 6.4072135e-01, 6.3063547e-01,
    6.2061795e-01, 6.1067030e-01, 6.0079402e-01, 5.9099055e-01, 5.8126130e-01,
    5.7160764e-01, 5.6203091e-01, 5.5253238e-01, 5.4311331e-01, 5.3377488e-01,
    5.2451828e-01, 5.1534461e-01, 5.0625495e-01, 4.9725033e-01, 4.8833174e-01,
    4.7950012e-01, 4.7075638e-01, 4.6210137e-01, 4.5353590e-01, 4.4506075e-01,
    4.3667663e-01, 4.2838424e-01, 4.2018419e-01, 4.1207710e-01, 4.0406350e-01,
    3.9614391e-01, 3.8831878e-01, 3.8058854e-01, 3.7295356e-01, 3.6541417e-01,
    3.5797067e-01, 3.5062331e-01, 3.4337230e-01, 3.3621780e-01, 3.2915994e-01,
    3.2219881e-01, 3.1533445e-01, 3.0856688e-01, 3.0189606e-01, 2.9532192e-01,
    2.8884437e-01, 2.8246325e-01, 2.7617839e-01, 2.6998957e-01, 2.6389655e-01,
    2.5789904e-01, 2.5199672e-01, 2.4618925e-01, 2.4047624e-01, 2.3485729e-01,
    2.2933194e-01, 2.2389973e-01, 2.1856015e-01, 2.1331268e-01, 2.0815675e-01,
    2.0309179e-01, 1.9811717e-01, 1.9323228e-01, 1.8843644e-01, 1.8372898e-01,
    1.7910919e-01, 1.7457635e-01, 1.7012971e-01, 1.6576850e-01, 1.6149193e-01,
    1.5729921e-01, 1.5318950e-01, 1.4916198e-01, 1.4521579e-01, 1.4135005e-01,
    1.3756389e-01, 1.3385641e-01, 1.3022670e-01, 1.2667384e-01, 1.2319690e-01,
    1.1979493e-01, 1.1646699e-01, 1.1321211e-01, 1.1002933e-01, 1.0691767e-01,
    1.0387616e-01, 1.0090380e-01, 9.7999601e-02, 9.5162573e-02, 9.2391714e-02,
    8.9686022e-02, 8.7044492e-02, 8.4466119e-02, 8.1949896e-02, 7.9494816e-02,
    7.7099872e-02, 7.4764058e-02, 7.2486371e-02, 7.0265807e-02, 6.8101367e-02,
    6.5992055e-02, 6.3936877e-02, 6.1934845e-02, 5.9984974e-02, 5.8086285e-02,
    5.6237804e-02, 5.4438563e-02, 5.2687602e-02, 5.0983965e-02, 4.9326704e-02,
    4.7714880e-02, 4.6147561e-02, 4.4623821e-02, 4.3142747e-02, 4.1703430e-02,
    4.0304974e-02, 3.8946490e-02, 3.7627100e-02, 3.6345935e-02, 3.5102135e-02,
    3.3894854e-02, 3.2723252e-02, 3.1586503e-02, 3.0483791e-02, 2.9414310e-02,
    2.8377267e-02, 2.7371878e-02, 2.6397373e-02, 2.5452991e-02, 2.4537984e-02,
    2.3651617e-02, 2.2793163e-02, 2.1961912e-02, 2.1157160e-02, 2.0378220e-02,
    1.9624415e-02, 1.8895079e-02, 1.8189558e-02, 1.7507213e-02, 1.6847413e-02,
    1.6209541e-02, 1.5592992e-02, 1.4997173e-02, 1.4421500e-02, 1.3865405e-02,
    1.3328329e-02, 1.2809725e-02, 1.2309058e-02, 1.1825804e-02, 1.1359451e-02,
    1.0909498e-02, 1.0475455e-02, 1.0056844e-02, 9.6531949e-03, 9.2640524e-03,
    8.8889699e-03, 8.5275117e-03, 8.1792524e-03, 7.8437772e-03, 7.5206816e-03,
    7.2095708e-03, 6.9100602e-03, 6.6217749e-03, 6.3443498e-03, 6.0774291e-03,
    5.8206664e-03, 5.5737245e-03, 5.3362754e-03, 5.1079996e-03, 4.8885868e-03,
    4.6777350e-03, 4.4751506e-03, 4.2805485e-03, 4.0936516e-03, 3.9141905e-03,
    3.7419040e-03, 3.5765382e-03, 3.4178470e-03, 3.2655913e-03, 3.1195395e-03,
    2.9794667e-03, 2.8451550e-03, 2.7163932e-03, 2.5929767e-03, 2.4747073e-03,
    2.3613930e-03, 2.2528478e-03, 2.1488918e-03, 2.0493509e-03, 1.9540568e-03,
    1.8628463e-03, 1.7755620e-03, 1.6920516e-03, 1.6121679e-03, 1.5357687e-03,
    1.4627166e-03, 1.3928789e-03, 1.3261275e-03, 1.2623388e-03, 1.2013936e-03,
    1.1431766e-03, 1.0875769e-03, 1.0344874e-03, 9.8380499e-04, 9.3543014e-04,
    8.8926703e-04, 8.4522336e-04, 8.0321022e-04, 7.6314201e-04, 7.2493633e-04,
    6.8851390e-04, 6.5379842e-04, 6.2071651e-04, 5.8919761e-04, 5.5917388e-04,
    5.3058011e-04, 5.0335364e-04, 4.7743427e-04, 4.5276419e-04, 4.2928787e-04,
    4.0695202e-04, 3.8570548e-04, 3.6549918e-04, 3.4628602e-04, 3.2802084e-04,
    3.1066034e-04, 2.9416302e-04, 2.7848909e-04, 2.6360043e-04, 2.4946053e-04,
    2.3603442e-04, 2.2328861e-04, 2.1119106e-04, 1.9971108e-04, 1.8881934e-04,
    1.7848775e-04, 1.6868947e-04, 1.5939883e-04, 1.5059129e-04, 1.4224339e-04,
    1.3433274e-04, 1.2683793e-04, 1.1973851e-04, 1.1301499e-04, 1.0664871e-04,
    1.0062192e-04, 9.4917648e-05, 8.9519712e-05, 8.4412684e-05, 7.9581853e-05,
    7.5013195e-05, 7.0693346e-05, 6.6609573e-05, 6.2749746e-05, 5.9102315e-05,
    5.5656280e-05, 5.2401173e-05, 4.9327030e-05, 4.6424372e-05, 4.3684180e-05,
    4.1097878e-05, 3.8657312e-05, 3.6354731e-05, 3.4182767e-05, 3.2134420e-05,
    3.0203042e-05, 2.8382317e-05, 2.6666249e-05, 2.5049145e-05, 2.3525603e-05,
    2.2090497e-05, 2.0738964e-05, 1.9466391e-05, 1.8268405e-05, 1.7140860e-05,
    1.6079826e-05, 1.5081579e-05, 1.4142593e-05, 1.3259525e-05, 1.2429212e-05,
    1.1648657e-05, 1.0915027e-05, 1.0225638e-05, 9.5779508e-06, 8.9695656e-06,
    8.3982113e-06, 7.8617414e-06, 7.3581267e-06, 6.8854496e-06, 6.4418982e-06,
    6.0257612e-06, 5.6354221e-06, 5.2693549e-06, 4.9261191e-06, 4.6043549e-06,
    4.3027795e-06, 4.0201827e-06, 3.7554231e-06, 3.5074244e-06, 3.2751721e-06,
    3.0577098e-06, 2.8541364e-06, 2.6636030e-06, 2.4853099e-06, 2.3185041e-06,
    2.1624768e-06, 2.0165607e-06, 1.8801277e-06, 1.7525872e-06, 1.6333833e-06,
    1.5219934e-06, 1.4179261e-06, 1.3207194e-06, 1.2299393e-06, 1.1451779e-06,
    1.0660518e-06, 9.9220124e-07, 9.2328825e-07, 8.5899557e-07, 7.9902542e-07,
    7.4309837e-07, 6.9095228e-07, 6.4234125e-07, 5.9703470e-07, 5.5481644e-07,
    5.1548382e-07, 4.7884695e-07, 4.4472789e-07, 4.1295995e-07, 3.8338704e-07,
    3.5586299e-07, 3.3025099e-07, 3.0642297e-07, 2.8425909e-07, 2.6364727e-07,
    2.4448265e-07, 2.2666718e-07, 2.1010920e-07, 1.9472302e-07, 1.8042857e-07,
    1.6715106e-07, 1.5482059e-07, 1.4337191e-07, 1.3274408e-07, 1.2288023e-07,
    1.1372726e-07, 1.0523564e-07, 9.7359161e-08, 9.0054724e-08, 8.3282135e-08,
    7.7003927e-08, 7.1185175e-08, 6.5793333e-08, 6.0798078e-08, 5.6171167e-08,
    5.1886293e-08, 4.7918968e-08, 4.4246391e-08, 4.0847345e-08, 3.7702087e-08,
    3.4792249e-08, 3.2100749e-08, 2.9611701e-08, 2.7310339e-08, 2.5182935e-08,
    2.3216732e-08, 2.1399880e-08, 1.9721370e-08, 1.8170978e-08, 1.6739211e-08,
    1.5417258e-08, ]

_kErfcInvArgs = \
   [1.0000000e-03, 1.5000000e-03, 2.0000000e-03, 2.5000000e-03, 3.0000000e-03,
    3.5000000e-03, 4.0000000e-03, 4.5000000e-03, 5.0000000e-03, 5.5000000e-03,
    6.0000000e-03, 6.5000000e-03, 7.0000000e-03, 7.5000000e-03, 8.0000000e-03,
    8.5000000e-03, 9.0000000e-03, 9.5000000e-03, 1.0000000e-02, 1.0500000e-02,
    1.1000000e-02, 1.1500000e-02, 1.2000000e-02, 1.2500000e-02, 1.3000000e-02,
    1.3500000e-02, 1.4000000e-02, 1.4500000e-02, 1.5000000e-02, 1.5500000e-02,
    1.6000000e-02, 1.6500000e-02, 1.7000000e-02, 1.7500000e-02, 1.8000000e-02,
    1.8500000e-02, 1.9000000e-02, 1.9500000e-02, 2.0000000e-02, 2.0500000e-02,
    2.1000000e-02, 2.1500000e-02, 2.2000000e-02, 2.2500000e-02, 2.3000000e-02,
    2.3500000e-02, 2.4000000e-02, 2.4500000e-02, 2.5000000e-02, 2.5500000e-02,
    2.6000000e-02, 2.6500000e-02, 2.7000000e-02, 2.7500000e-02, 2.8000000e-02,
    2.8500000e-02, 2.9000000e-02, 2.9500000e-02, 3.0000000e-02, 3.0500000e-02,
    3.1000000e-02, 3.1500000e-02, 3.2000000e-02, 3.2500000e-02, 3.3000000e-02,
    3.3500000e-02, 3.4000000e-02, 3.4500000e-02, 3.5000000e-02, 3.5500000e-02,
    3.6000000e-02, 3.6500000e-02, 3.7000000e-02, 3.7500000e-02, 3.8000000e-02,
    3.8500000e-02, 3.9000000e-02, 3.9500000e-02, 4.0000000e-02, 4.0500000e-02,
    4.1000000e-02, 4.1500000e-02, 4.2000000e-02, 4.2500000e-02, 4.3000000e-02,
    4.3500000e-02, 4.4000000e-02, 4.4500000e-02, 4.5000000e-02, 4.5500000e-02,
    4.6000000e-02, 4.6500000e-02, 4.7000000e-02, 4.7500000e-02, 4.8000000e-02,
    4.8500000e-02, 4.9000000e-02, 4.9500000e-02, 5.0000000e-02, 5.0500000e-02,
    5.1000000e-02, 5.1500000e-02, 5.2000000e-02, 5.2500000e-02, 5.3000000e-02,
    5.3500000e-02, 5.4000000e-02, 5.4500000e-02, 5.5000000e-02, 5.5500000e-02,
    5.6000000e-02, 5.6500000e-02, 5.7000000e-02, 5.7500000e-02, 5.8000000e-02,
    5.8500000e-02, 5.9000000e-02, 5.9500000e-02, 6.0000000e-02, 6.0500000e-02,
    6.1000000e-02, 6.1500000e-02, 6.2000000e-02, 6.2500000e-02, 6.3000000e-02,
    6.3500000e-02, 6.4000000e-02, 6.4500000e-02, 6.5000000e-02, 6.5500000e-02,
    6.6000000e-02, 6.6500000e-02, 6.7000000e-02, 6.7500000e-02, 6.8000000e-02,
    6.8500000e-02, 6.9000000e-02, 6.9500000e-02, 7.0000000e-02, 7.0500000e-02,
    7.1000000e-02, 7.1500000e-02, 7.2000000e-02, 7.2500000e-02, 7.3000000e-02,
    7.3500000e-02, 7.4000000e-02, 7.4500000e-02, 7.5000000e-02, 7.5500000e-02,
    7.6000000e-02, 7.6500000e-02, 7.7000000e-02, 7.7500000e-02, 7.8000000e-02,
    7.8500000e-02, 7.9000000e-02, 7.9500000e-02, 8.0000000e-02, 8.0500000e-02,
    8.1000000e-02, 8.1500000e-02, 8.2000000e-02, 8.2500000e-02, 8.3000000e-02,
    8.3500000e-02, 8.4000000e-02, 8.4500000e-02, 8.5000000e-02, 8.5500000e-02,
    8.6000000e-02, 8.6500000e-02, 8.7000000e-02, 8.7500000e-02, 8.8000000e-02,
    8.8500000e-02, 8.9000000e-02, 8.9500000e-02, 9.0000000e-02, 9.0500000e-02,
    9.1000000e-02, 9.1500000e-02, 9.2000000e-02, 9.2500000e-02, 9.3000000e-02,
    9.3500000e-02, 9.4000000e-02, 9.4500000e-02, 9.5000000e-02, 9.5500000e-02,
    9.6000000e-02, 9.6500000e-02, 9.7000000e-02, 9.7500000e-02, 9.8000000e-02,
    9.8500000e-02, 9.9000000e-02, 9.9500000e-02, 1.0000000e-01, ]

_kErfcInvVals = \
   [2.3267538e+00, 2.2448403e+00, 2.1851242e+00, 2.1378252e+00, 2.0985076e+00,
    2.0647716e+00, 2.0351677e+00, 2.0087516e+00, 1.9848726e+00, 1.9630630e+00,
    1.9429749e+00, 1.9243421e+00, 1.9069569e+00, 1.8906531e+00, 1.8752965e+00,
    1.8607766e+00, 1.8470012e+00, 1.8338931e+00, 1.8213864e+00, 1.8094248e+00,
    1.7979596e+00, 1.7869484e+00, 1.7763543e+00, 1.7661445e+00, 1.7562901e+00,
    1.7467655e+00, 1.7375476e+00, 1.7286159e+00, 1.7199517e+00, 1.7115384e+00,
    1.7033605e+00, 1.6954044e+00, 1.6876572e+00, 1.6801075e+00, 1.6727446e+00,
    1.6655587e+00, 1.6585409e+00, 1.6516826e+00, 1.6449764e+00, 1.6384149e+00,
    1.6319915e+00, 1.6257000e+00, 1.6195347e+00, 1.6134900e+00, 1.6075611e+00,
    1.6017430e+00, 1.5960314e+00, 1.5904221e+00, 1.5849111e+00, 1.5794947e+00,
    1.5741694e+00, 1.5689320e+00, 1.5637792e+00, 1.5587082e+00, 1.5537161e+00,
    1.5488002e+00, 1.5439581e+00, 1.5391873e+00, 1.5344856e+00, 1.5298508e+00,
    1.5252807e+00, 1.5207735e+00, 1.5163273e+00, 1.5119402e+00, 1.5076106e+00,
    1.5033367e+00, 1.4991171e+00, 1.4949502e+00, 1.4908345e+00, 1.4867688e+00,
    1.4827516e+00, 1.4787817e+00, 1.4748579e+00, 1.4709790e+00, 1.4671439e+00,
    1.4633514e+00, 1.4596005e+00, 1.4558903e+00, 1.4522198e+00, 1.4485879e+00,
    1.4449939e+00, 1.4414369e+00, 1.4379159e+00, 1.4344302e+00, 1.4309791e+00,
    1.4275617e+00, 1.4241773e+00, 1.4208252e+00, 1.4175048e+00, 1.4142153e+00,
    1.4109561e+00, 1.4077267e+00, 1.4045263e+00, 1.4013545e+00, 1.3982106e+00,
    1.3950941e+00, 1.3920045e+00, 1.3889412e+00, 1.3859038e+00, 1.3828918e+00,
    1.3799046e+00, 1.3769418e+00, 1.3740031e+00, 1.3710878e+00, 1.3681957e+00,
    1.3653263e+00, 1.3624792e+00, 1.3596540e+00, 1.3568504e+00, 1.3540679e+00,
    1.3513063e+00, 1.3485651e+00, 1.3458440e+00, 1.3431427e+00, 1.3404609e+00,
    1.3377982e+00, 1.3351543e+00, 1.3325290e+00, 1.3299219e+00, 1.3273328e+00,
    1.3247613e+00, 1.3222073e+00, 1.3196704e+00, 1.3171503e+00, 1.3146469e+00,
    1.3121599e+00, 1.3096889e+00, 1.3072339e+00, 1.3047945e+00, 1.3023706e+00,
    1.2999618e+00, 1.2975681e+00, 1.2951891e+00, 1.2928247e+00, 1.2904747e+00,
    1.2881388e+00, 1.2858169e+00, 1.2835088e+00, 1.2812143e+00, 1.2789332e+00,
    1.2766654e+00, 1.2744105e+00, 1.2721686e+00, 1.2699394e+00, 1.2677227e+00,
    1.2655185e+00, 1.2633264e+00, 1.2611465e+00, 1.2589784e+00, 1.2568221e+00,
    1.2546775e+00, 1.2525443e+00, 1.2504225e+00, 1.2483118e+00, 1.2462123e+00,
    1.2441236e+00, 1.2420458e+00, 1.2399786e+00, 1.2379220e+00, 1.2358758e+00,
    1.2338399e+00, 1.2318141e+00, 1.2297985e+00, 1.2277927e+00, 1.2257968e+00,
    1.2238106e+00, 1.2218341e+00, 1.2198670e+00, 1.2179093e+00, 1.2159609e+00,
    1.2140217e+00, 1.2120916e+00, 1.2101705e+00, 1.2082583e+00, 1.2063549e+00,
    1.2044601e+00, 1.2025740e+00, 1.2006964e+00, 1.1988272e+00, 1.1969664e+00,
    1.1951138e+00, 1.1932694e+00, 1.1914330e+00, 1.1896047e+00, 1.1877843e+00,
    1.1859717e+00, 1.1841669e+00, 1.1823698e+00, 1.1805802e+00, 1.1787982e+00,
    1.1770237e+00, 1.1752565e+00, 1.1734967e+00, 1.1717441e+00, 1.1699986e+00,
    1.1682603e+00, 1.1665290e+00, 1.1648046e+00, 1.1630872e+00, ]


def computeAccuracies(numCategories, predictionMatrix):
    """This function calculates

       (1) the accuracy and standard error for each category; and
       (2) the overall accuracy and standard error for the entire
           data set.

       NOTES:
       - All accuracy and standard errors are computed as decimals
         (not percentages).

       - The categories are assumed to lie in the range [0, numCategories).
         Any entries in the prediction matrix that correspond to inputs
         outside the valid range are ignored.

       - If any categories have too few data points (i.e. numCorrect_i < 5
         or (numInputs_i-numCorrect_i) < 5), the accuracy and stdErr for
         that category are set to -1 and -1, respectively, to indicate
         that no meaningful statistics can be computed for that category.

       - The overall accuracy for the entire data sets is computed using
         the formula:

           accuracyOverall = totalCorrect / totalInputs

       - The overall standard error for the entire data sets is computed
         using one of two methods.  If there are enough data points so
         that numCorrect_i >= 5 and (numInputs_i-numCorrect_i) >= 5 for
         ALL categories, the following formula is used:

           stdErrOverall = sum( (numInputs_i*stdErr_i)**2 ) / totalInputs

         This formula approximates the number of correct predictions
         for each category as a normal distribution with

           mean     = numCorrect_i

           variance = numInputs_i*(accuracy_i)*(1 - accuracy_i)

         When there are not enough data points, we compute the standard
         error when the data from all categories are pooled:

           stdErrOverall = sum( accOverall*(1-accOverall)/totalInputs )

         When applicable, the first formula generally yields a smaller
         standard error than the second formula.


       @param  numCategories        Number of categories of inputs
       @param  predictionMatrix     Dictionary that represents a matrix
                                    whose (i,j)-th entry is the number
                                    of predictions of j-th category j for
                                    inputs from i-th category.

       @return results              List containing tuples of the form
                                    (accuracy, stdErr).  The accuracy and
                                    standard error for the i-th category is
                                    stored in the i-th element of the list.
                                    The last element of the list holds the
                                    pooled accuracy and standard error for
                                    entire data set.
    """
    # collect statistics from predictionMatrix and store it in a
    # dictionary where the key is the category number and the value
    # is a tuple of the form [numCorrect, numInputs].
    categoryCounts = {}
    for idx, count in predictionMatrix.iteritems():

        # get input category
        category = idx[0]

        if categoryCounts.has_key(category):
            # category already seen, so appropriately increment
            # numCorrect and numInputs
            currentCounts = categoryCounts[category]
            numInputs = currentCounts[1] + count
            if idx[0] == idx[1]:
                numCorrect = currentCounts[0] + count
            else:
                numCorrect = currentCounts[0]
        else:
            # category never seen before
            numInputs = count
            if idx[0] == idx[1]:
                numCorrect = count
            else:
                numCorrect = 0

        # update statistics for category
        categoryCounts[category] = [numCorrect, numInputs]

    # compute accuracy and stdErr for each category and collect data
    # for computing overall accuracy and stdErr
    results = [(-1,-1)]*(numCategories+1)  # initialize with invalid data
    totalCorrect  = 0
    totalInputs   = 0
    totalVariance = 0
    poolDataForOverallStdErr = False
    for category, counts in categoryCounts.iteritems():
        if category >= 0 and category < numCategories:

            # get number of correct predictions and number of inputs
            numCorrect  = counts[0]
            numInputs = counts[1]

            # collect counts for overall accuracy and stdErr
            totalCorrect += numCorrect
            totalInputs += numInputs

            # check that there are enough data points to
            # compute meaningful statistics
            if numCorrect >= 5 and (numInputs-numCorrect) >= 5:
                # case:  enough data points for category

                # accuracy and stdErr for category
                accuracy = 1.0*numCorrect/numInputs
                stdErr   = sqrt(accuracy*(1-accuracy)/numInputs)
                results[category] = (accuracy, stdErr)

                # accumulate contribution to variance for overall
                # data set
                totalVariance += numInputs*accuracy*(1-accuracy)

            else:
                # case:  not enough data points for category

                # leave results[category] set to (-1,-1)

                # use pooled data to compute overall standard error
                poolDataForOverallStdErr = True

    # compute accuracy and stdErr for entire data set
    accuracyOverall = 1.0*totalCorrect/totalInputs
    if poolDataForOverallStdErr:
        stdErrOverall = sqrt(accuracyOverall*(1-accuracyOverall)/totalInputs)
    else:
        stdErrOverall = sqrt(totalVariance)/totalInputs
    results[-1] = (accuracyOverall, stdErrOverall)

    return results


def computeConfidenceIntervals(meansAndStdErrs, confidenceLevel,
                               isProportionData = False):
    """This function calculates the confidence interval for each mean
       and standard error at the specified confidence level.

       NOTES:
       - This function can also be used to compute the confidence
         interval for any random variable that has a distribution that
         is approximately normal.  For example, we can use this function
         to calculate the confidence interval for an estimate of the
         probability of success in a Bernoulli trial.  This is the
         statistical model we use to measure the accuracy of a prediction
         system.

       - When the stdErr is -1, the mean and stdErr are assumed to be
         statistically meaningless and the confidence interval is set to
         (-1, -1).

       - The end points of the confidence interval are only known to
         within approximately 0.006.  This limitation comes from two
         sources:  (1) the linear interpolation used to estimate
         z when p = confidenceLevel/2 >= 0.001 and (2) the asymptotic
         approximation used to estimate z when p < 0.001.  For more
         details, see the documentation for the _erfcinv() function.

       @param  meansAndStdErrs      List of tuples of the form (mean, stdErr)
       @param  confidenceLevel      The confidence level to use when computing
                                    confidence intervals.  The confidenceLevel
                                    must be a real number >= 0.9 and < 1.0.
                                    Commonly used confidence levels are 0.95
                                    and 0.99.
       @param  isProportionData     Boolean indicating whether or not the
                                    means are really proportions.  When set
                                    to True, the endpoints of the confidence
                                    intervals are restricted to be between
                                    0 and 1.

       @return confidenceIntervals  List containing the confidence intervals
                                    for each set of data.  The confidence
                                    interval for each (mean, stdErrs) pair
                                    is stored as a tuple of the form
                                    (lo, hi).
    """
    # check that confidenceLevel is in valid range
    assert confidenceLevel >= 0.9 and confidenceLevel < 1.0

    # Compute z value which yields the desired confidence level for
    # a standard normal distribution.  That is, find z such that
    # Prob(|Z| < z) = 1 - erfc(z/sqrt(2)) = confidenceLevel.
    z = computeZValueForStdNormal(1-confidenceLevel)

    # Compute confidence intervals
    confidenceIntervals = []
    for mean, stdErr in meansAndStdErrs:
        if stdErr != -1:
            # case:  statistically meaningful data
            lowerEnd = mean - z*stdErr
            upperEnd = mean + z*stdErr
            if isProportionData:
                if lowerEnd < 0.0:
                    lowerEnd = 0.0
                if upperEnd > 1.0:
                    upperEnd = 1.0
            confidenceIntervals.append( (lowerEnd, upperEnd) )

        else:
            # case:  statistically meaningless data
            confidenceIntervals.append( (-1, -1) )

    return confidenceIntervals


def computePValueForStdNormal(z):
    """Computes the p-value associated with z for a the standard
       normal distribution.  The result is accurate to within 2e-5.
       For more details about the error, see the documentation for the
       _erfc() function.

       NOTES:
       - Because of the definition of the standard normal distribution,
         p = erfc(z/sqrt(2))

       @param  z  z-value

       @return p  p-value = probability that a random variable having a
                  standard normal distribution has a value with |Z| > |z|.
    """

    return _erfc(z/_kSqrtTwo)


def computeZValueForStdNormal(p):
    """Computes the z-value associated with p for a the standard
       normal distribution for p in the range (0.0, 0.1].  The result is
       accurate to within 0.006.  For more details about the error, see
       the documentation for the _erfcinv() function.

       NOTES:
       - Because of the definition of the standard normal distribution,
         z = sqrt(2)*erfcinv(p)

       @param  p  p-value = probability that a random variable having a
                  standard normal distribution has a value with |Z| > z.

       @return z  z value associated with p.
    """

    return _kSqrtTwo*_erfcinv(p)


def _erfc(x):
    """Approximation of the complimentary error function x in the range
       [0.0, infinity).  The result is accurate to within 2e-5.

       NOTES:
       - The approximation for the complementary error function uses
         the following algorithm:

         * when x < 4, use linear interpolation of high-accuracy
           values of the erfc() function at 401 uniformly spaced
           x-values in the interval [0.0, 4.0].

         * when x >= 4, use the asymptotic approximation erfc(x)

           erfc(x) ~ 1/sqrt(pi)*exp(-x^2)*(2*x^2-1)/(2*x^3)

       @param  x  Argument of complementary error function
                  corresponding to p.

       @return p  Value of complimentary error function.
    """
    # Use linear interpolation to approximate p if x < 4.0
    if x < 4.0:
        i = int((x - _kXLo)/_kDeltaX)  # compute index of element in
                                       # _kErfcArgs which satisfies
                                       # _kErfcArgs(i) <= x < _kErfcArgs(i+1)
        p = _kErfcVals[i]   * (_kErfcArgs[i+1] - x) / _kDeltaX  \
          + _kErfcVals[i+1] * (x - _kErfcArgs[i])   / _kDeltaX
    else:
        p = exp(-x**2)/_kSqrtPi*(1/x - 0.5/x**3)

    return p


def _erfcinv(p):
    """Approximation of the inverse of the complimentary error function
       for p in the range (0.0, 0.1].  The result is accurate to within
       0.005.

       NOTES:
       - The approximation for the inverse of the complementary error
         function uses the following algorithm:

         * when p >= 0.001, use linear interpolation of high-accuracy
           values of the erfcinv() function at 199 uniformly spaced
           p-values in the interval [0.001, 0.1]

         * when p < 0.001, use Newton iteration to solve for the value
           of x which makes the asymptotic approximation erfc(x) equal
           to p.  The asymptotic approximation used is

           erfc(x) ~ 1/sqrt(pi)*exp(-x^2)*(2*x^2-1)/(2*x^3)

           and the initial iterate is obtained by linear extrapolation
           of the high-accuracy values.

       @param  p  Value of complimentary error function.

       @return x  Argument of complementary error function
                  corresponding to p.
    """
    # check that p <= 0.1
    assert p <= 0.1

    # if p == 0.1, return the high-accuracy value
    if (p == 0.1):
        return _kErfcInvVals[-1]

    # if p == 0.0, return a really big number
    if (p == 0.0):
        return _kBigNumber

    # Use linear interpolation to approximate x.
    i = int((p - _kPLo)/_kDeltaP)  # compute index of element in
                                   # _kErfcInvArgs which satisfies
                                   # _kErfcInvArgs(i) <= p < _kErfcInvArgs(i+1)
    if (i < 0):
        i = 0
    x = _kErfcInvVals[i]   * (_kErfcInvArgs[i+1] - p) / _kDeltaP  \
      + _kErfcInvVals[i+1] * (p - _kErfcInvArgs[i])   / _kDeltaP

    # Use Newton iteration on asymptotic approximation to erfc(x) if
    # p < 0.001.
    if (p < 0.001):
        resTol   = 1e-8
        maxIters = 100
        res = 2*p*x**3/(2*x**2-1) - exp(-x**2)/_kSqrtPi
        count = 0
        while fabs(res) > resTol and count < maxIters:
             DresDx = p*(4*x**4-6*x**2)/(2*x**2-1)**2   \
                     + 2*x*exp(-x**2)/_kSqrtPi
             x = x - res/DresDx
             res = 2*p*x**3/(2*x**2-1) - exp(-x**2)/_kSqrtPi
             count += 1

    return x


##############################################################################
def _test_main():
    """OB_REDACT
    Our main function, which runs test code
    """

    _testErfcAndComputePValueForStdNormal()
    _testErfcInvAndComputeZValueForStdNormal()
    _testComputeConfidenceIntervalsAndComputeAccuracies()

    print "------------------------------------------------"

    return


def _testErfcAndComputePValueForStdNormal():
    """OB_REDACT
    Test code for _erfc() and computePValueForStdNormal() functions.
    """
    print "------------------------------------------------"
    print "Testing _erfc()"
    errTol = 2.e-5
    xVals = [9e5, 7.34e4, 342., 72., 15., 8., 5.5, 4.000001, 4.0, 3.99999999,
             3.123413274340875, 2.811658633703122, 2.751063905712061,
             2.556403150920201, 2.629741776210273, 2.347632779824492,
             2.326753765513525, 1.821386367718450, 1.820653819567649,
             1.383472938549021, 1.180765992282422, 1.163087153676674,
             1.08, 0.75, 0.23, 0.0017, 0.0001, 0.0]
    pVals = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 7.357847917974398e-15,
             1.541713091844121e-08,  1.541725790028002e-08,
             1.541725917010353e-08, 1e-5, 7e-5, 1e-4, 3e-4, 0.0002,
             0.0009, 0.001, 0.01, 0.01003, 0.0504032, 0.094948, 0.1,
             0.126673841612110, 0.288844366346485, 0.744977400407727,
             0.998081757263845, 0.999887162083667, 1.000000000000000]
    for i in xrange(0, len(xVals)):
        x = xVals[i]
        print "  x =", x, "...",

        p = _erfc(x)
        assert fabs(p-pVals[i]) < errTol
        print "PASS"  # test passed


    ############################################################
    print "------------------------------------------------"
    print "Testing computePValueForStdNormal()"
    errTol = 2.e-5
    zVals = [1.272792206135786e6, 1.038032754781852e5, 483.6610383315985,
             101.8233764908629, 21.213203435596427, 11.313708498984761,
             7.778174593052023, 5.656855663705943, 5.656854249492381,
             5.656854235350245, 4.417173413469023, 3.976285772546361,
             3.890591886413095, 3.615300006924663, 3.719016485455681,
             3.320054116699447, 3.290526731491896, 2.575829303548902,
             2.574793324018947, 1.956526192872185, 1.669855280274727,
             1.644853626951473, 1.527350647362943, 1.060660171779821,
             0.325269119345812, 0.002404163056034, 0.000141421356237, 0.0]
    pVals = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 7.357847917974398e-15,
             1.541713091844121e-08,  1.541725790028002e-08,
             1.541725917010353e-08, 1e-5, 7e-5, 1e-4, 3e-4, 0.0002,
             0.0009, 0.001, 0.01, 0.01003, 0.0504032, 0.094948, 0.1,
             0.126673841612110, 0.288844366346485, 0.744977400407727,
             0.998081757263845, 0.999887162083667, 1.000000000000000]
    for i in xrange(0, len(zVals)):
        z = zVals[i]
        print "  z =", z, "...",

        p = computePValueForStdNormal(z)
        assert fabs(p-pVals[i]) < errTol
        print "PASS"  # test passed


def _testErfcInvAndComputeZValueForStdNormal():
    """OB_REDACT
    Test code for _erfcinv() and computeZValueForStdNormal() functions.
    """
    print "------------------------------------------------"
    print "Testing _erfcinv() and computeZValueForStdNormal()"
    errTol = 0.006
    pVals = [1e-5, 7e-5, 1e-4, 3e-4, 0.0002, 0.0009, 0.001,
             0.01, 0.01003, 0.0504032, 0.094948, 0.1]
    xVals = [3.123413274340875, 2.811658633703122, 2.751063905712061,
             2.556403150920201, 2.629741776210273, 2.347632779824492,
             2.326753765513525, 1.821386367718450, 1.820653819567649,
             1.383472938549021, 1.180765992282422, 1.163087153676674]
    zVals = [4.417173413469023, 3.976285772546361, 3.890591886413095,
             3.615300006924663, 3.719016485455681, 3.320054116699447,
             3.290526731491896, 2.575829303548902, 2.574793324018947,
             1.956526192872185, 1.669855280274727, 1.644853626951473]
    for i in xrange(0, len(pVals)):
        p = pVals[i]
        print "  p =", p, "...",

        x = _erfcinv(p)
        z = computeZValueForStdNormal(p)
        assert fabs(x-xVals[i]) < errTol
        assert fabs(z-zVals[i]) < errTol
        print "PASS"  # test passed

    p = 0.0
    print "  p =", p, "...",
    xInf = _erfcinv(p)
    assert fabs(xInf-_kBigNumber) < errTol
    zInf = computeZValueForStdNormal(p)
    assert fabs(zInf-_kSqrtTwo*_kBigNumber) < errTol
    print "PASS"  # test passed


def _testComputeConfidenceIntervalsAndComputeAccuracies(): #PYCHECKER too many lines; long function a result of size of test data
    """OB_REDACT
    Test code for computeConfidenceIntervals() and computeAccuracies()
    functions.
    """
    print "------------------------------------------------"
    print "Testing computeConfidenceIntervals() for Non-proportion Data"
    errTol = 1e-5
    meansAndStdErrs   = [(0.5, 0.1),
                         (0.8, 0.4),
                         (0.12, 0.1),
                         (0.89, 0.3)]
    confidenceLevels = [0.95, 0.97, 0.99, 0.997]
    confIntsCorrect = [  \
        [(0.304003601545995, 0.695996398454005),
         (0.016014406183978, 1.583985593816022),
         (-0.075996398454005, 0.315996398454005),
         (0.302010804637984, 1.477989195362016)],
        [(0.282990962241544, 0.717009037758456),
         (-0.068036151033824, 1.668036151033824),
         (-0.097009037758456, 0.337009037758456),
         (0.238972886724632, 1.541027113275368)],
        [(0.242417069645110, 0.757582930354890),
         (-0.230331721419560, 1.830331721419560),
         (-0.137582930354890, 0.377582930354890),
         (0.117251208935330, 1.662748791064670)],
        [(0.203226207465822, 0.796773792534178),
         (-0.387095170136713, 1.987095170136713),
         (-0.176773792534178, 0.416773792534178),
         (-0.000321377602535, 1.780321377602535)] ]


    for i in xrange(len(confidenceLevels)):
        confidence = confidenceLevels[i]
        print "  confidenceLevel =", confidence, "...",
        confIntervals = computeConfidenceIntervals(meansAndStdErrs,
                                                   confidenceLevel = confidence,
                                                   isProportionData = False)
        allTestsPassed = True
        for j in xrange(len(meansAndStdErrs)):
            confInt = confIntervals[j]
            confIntCorrect = confIntsCorrect[i][j]
            if (fabs(confInt[0]-confIntCorrect[0]) > errTol) or \
               (fabs(confInt[1]-confIntCorrect[1]) > errTol):
                allTestsPassed = False

        assert allTestsPassed
        print "PASS"  # test passed


    ############################################################
    print "------------------------------------------------"
    print "Testing computeConfidenceIntervals() for Proportion Data"
    errTol = 1e-5
    meansAndStdErrs   = [(0.5, 0.1),
                         (0.8, 0.4),
                         (0.12, 0.1),
                         (0.89, 0.3)]
    confidenceLevels = [0.95, 0.97, 0.99, 0.997]
    confIntsCorrect = [  \
        [(0.304003601545995, 0.695996398454005),
         (0.016014406183978, 1.0),
         (0.0, 0.315996398454005),
         (0.302010804637984, 1.0)],
        [(0.282990962241544, 0.717009037758456),
         (0.0, 1.0),
         (0.0, 0.337009037758456),
         (0.238972886724632, 1.0)],
        [(0.242417069645110, 0.757582930354890),
         (0.0, 1.0),
         (0.0, 0.377582930354890),
         (0.117251208935330, 1.0)],
        [(0.203226207465822, 0.796773792534178),
         (0.0, 1.0),
         (0.0, 0.416773792534178),
         (0.0, 1.0)] ]


    for i in xrange(len(confidenceLevels)):
        confidence = confidenceLevels[i]
        print "  confidenceLevel =", confidence, "...",
        confIntervals = computeConfidenceIntervals(meansAndStdErrs,
                                                   confidenceLevel = confidence,
                                                   isProportionData = True)
        allTestsPassed = True
        for j in xrange(len(meansAndStdErrs)):
            confInt = confIntervals[j]
            confIntCorrect = confIntsCorrect[i][j]
            if (fabs(confInt[0]-confIntCorrect[0]) > errTol) or \
               (fabs(confInt[1]-confIntCorrect[1]) > errTol):
                allTestsPassed = False

        assert allTestsPassed
        print "PASS"  # test passed


    ############################################################
    print "------------------------------------------------"
    print "Testing computeAccuracies()"
    errTol = 1e-5

    # this tests the case that at least one category has too few
    # data points that we need to pool the data when computing the
    # standard error
    predictionMatrix1 = {(27, 26): 2, (3, 25): 1, (13, 13): 3, (6, 6): 7,
                         (16, 9): 1, (19, 26): 1, (12, 12): 5, (13, 26): 6,
                         (7, 7): 8, (9, 9): 10, (6, 26): 2, (14, 26): 1,
                         (20, 24): 1, (25, 8): 1, (16, 24): 1, (23, 7): 3,
                         (11, 11): 8, (12, 3): 1, (27, 9): 3, (3, 3): 3,
                         (4, 4): 2, (5, 20): 4, (0, 0): 10, (8, 8): 10,
                         (20, 20): 7, (17, 24): 1, (19, 25): 2, (18, 9): 1,
                         (2, 2): 8, (20, 18): 1, (7, 9): 2, (19, 19): 2,
                         (1, 1): 9, (10, 9): 1, (22, 26): 3, (21, 26): 2,
                         (26, 26): 8, (12, 25): 4, (14, 14): 8, (20, 1): 1,
                         (14, 24): 1, (5, 24): 1, (25, 25): 9, (21, 21): 8,
                         (11, 26): 2, (24, 24): 10, (16, 16): 6, (26, 9): 1,
                         (13, 19): 1, (2, 24): 1, (1, 0): 1, (4, 20): 1,
                         (23, 24): 1, (6, 5): 1, (5, 5): 4, (2, 7): 1,
                         (22, 25): 2, (19, 9): 2, (16, 5): 1, (27, 27): 4,
                         (5, 16): 1, (22, 22): 4, (4, 1): 4, (10, 10): 9,
                         (3, 26): 6, (23, 23): 6, (15, 15): 10, (4, 26): 1,
                         (26, 5): 1, (16, 0): 1, (22, 8): 1, (18, 18): 9,
                         (4, 21): 2, (27, 25): 1, (19, 1): 3, (17, 17): 9}
    correctResults1 = [(-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (0.5, 0.158113883),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (-1, -1),
                       (0.7, 0.027386127)]  # statistics for entire data set
    print "  Categories with insufficient data...",
    accAndStdErrs1 = computeAccuracies(numCategories = 28,
                                       predictionMatrix = predictionMatrix1)
    allTestsPassed = True
    for i in xrange(len(accAndStdErrs1)):
        if (fabs(accAndStdErrs1[i][0]-correctResults1[i][0]) > errTol) or \
           (fabs(accAndStdErrs1[i][1]-correctResults1[i][1]) > errTol):
            allTestsPassed = False

    assert allTestsPassed
    print "PASS"  # test passed

    # this tests the case that all categories have enough data
    # that there is no need to pool the data when computing the
    # standard error
    predictionMatrix2 = {(0, 0): 70, (0, 3): 1, (0, 4): 1, (0, 5): 19,
                         (0, 8): 11, (0, 9): 123, (0, 11): 5,
                         (0, 13): 1, (0, 16): 55, (0, 17): 36,
                         (0, 19): 16, (0, 20): 8, (0, 23): 18,
                         (0, 25): 18, (0, 26): 4, (0, 27): 2,
                         (1, 1): 36, (1, 4): 28, (1, 5): 1,
                         (1, 11): 34, (1, 17): 183, (1, 20): 9,
                         (1, 23): 29, (1, 24): 3,
                         (2, 1): 3, (2, 2): 33, (2, 3): 9,
                         (2, 4): 6, (2, 7): 1, (2, 8): 8,
                         (2, 9): 42, (2, 10): 5, (2, 16): 3,
                         (2, 17): 197, (2, 19): 2, (2, 23): 27,
                         (2, 24): 15, (2, 26): 8, (2, 27): 5,
                         (3, 8): 14, (3, 3): 396, (3, 17): 31,
                         (3, 18): 11, (3, 22): 8, (3, 23): 6,
                         (3, 24): 2, (3, 27): 11}

    correctResults2 = [(0.180412371134021, 0.019521581197456),
                       (0.111455108359133, 0.017510091489258),
                       (0.090659340659341, 0.015049389806417),
                       (0.826722338204593, 0.017293518746723),
                       (0.344272844272844, 0.00882288303)]  # statistics for
                                                            # entire data set
    print "  Categories with sufficient data...",
    accAndStdErrs2 = computeAccuracies(numCategories = 4,
                                       predictionMatrix = predictionMatrix2)
    allTestsPassed = True
    for i in xrange(len(accAndStdErrs2)):
        if (fabs(accAndStdErrs2[i][0]-correctResults2[i][0]) > errTol) or \
           (fabs(accAndStdErrs2[i][1]-correctResults2[i][1]) > errTol):
            allTestsPassed = False

    assert allTestsPassed
    print "PASS"  # test passed


    ############################################################
    print "------------------------------------------------"
    print "Testing computeConfidenceIntervals()/computeAccuracies() interactions"

    print "  Categories with insufficient data...",
    errTol = 1e-5
    confidence = 0.95
    correctResults = [(-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (0.190102483864220, 0.809897516135780),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1),
                      (-1, -1)]
    del accAndStdErrs1[-1]
    confIntervals = computeConfidenceIntervals(meansAndStdErrs = accAndStdErrs1,
                                               confidenceLevel = confidence)
    allTestsPassed = True
    for i in xrange(len(confIntervals)):
        if (fabs(confIntervals[i][0]-correctResults[i][0]) > errTol) or \
           (fabs(confIntervals[i][1]-correctResults[i][1]) > errTol):
            allTestsPassed = False

    assert allTestsPassed
    print "PASS"  # test passed


    print "  Categories with sufficient data...",
    correctResults = [(0.142150071987007, 0.218674670281035),
                      (0.077135329040187, 0.145774887678079),
                      (0.061162536638764, 0.120156144679918),
                      (0.792827041461016, 0.860617634948170)]
    del accAndStdErrs2[-1]
    confIntervals = computeConfidenceIntervals(meansAndStdErrs = accAndStdErrs2,
                                               confidenceLevel = confidence)
    allTestsPassed = True
    for i in xrange(len(confIntervals)):
        if (fabs(confIntervals[i][0]-correctResults[i][0]) > errTol) or \
           (fabs(confIntervals[i][1]-correctResults[i][1]) > errTol):
            allTestsPassed = False

    assert allTestsPassed
    print "PASS"  # test passed


if __name__ == '__main__':
    _test_main()
