############## 基本的なモジュールのインポート ##############
from __future__ import print_function
from yade import pack, plot
from yade.gridpfacet import *
import numpy as np
import datetime
from pathlib import Path
import os
import sys

# ターミナルの出力が詰まっていて見づらいための区切り線
print("")
print("-------------------------------------")


############## 定数・変数の定義 (単位は全てSI単位系(長さはm, 時間はsec, 質量はkg)) ##############

### 粒子と粒子間の接触モデルに関する定数・変数 ###
# (要検討)摩擦角：粒子と粒子の間の摩擦角をラジアンで表現しています。この値は物性値として論文等で参照されるものです。
frictangle = 35 / 180 * np.pi

# 粒子の密度：単位体積あたりの質量を表す物性値です。この例では、kg/m^3の単位で表現されています。
density = 2650.0

# (要検討)ヤング率：粒子単体の硬さを示す物性値です。この例では、kPaの単位で表現されています。
young = 3e8

# 空間の各座標軸における直方体の境界の最大値です。
maxCorner_x = 0.075
maxCorner_y = 0.075
maxCorner_z = 0.025

# ポアソン比：粒子単体が応力を受けたときに、応力の方向に対して垂直な方向に起こるひずみと、応力の方向に沿ったひずみの比率を表す物性値です。
# 連続体力学で定義されるようなマクロなポアソン比ではありません。
poisson = 0.33

# 平均粒径：粒子の平均的な大きさを示すパラメータです。この値が大きいほど、粒子の大きさは大きくなります。
rMean = 0.001

# 粒径の分散：粒子の大きさのばらつきを示すパラメータです。この値が大きいほど、粒子の大きさは均一でなくなります。
# 0とすると粒径は全て同じになります。
rRelFuzz = 0

# 間隙比：粒子間の空隙の体積と粒子の体積の比を示す値です。この値が大きいほど、粒子間の空隙が多くなります。
# 圧密(密度調整)のステージが終了した後の目標間隙比ですが、2023/06/22時点では厳密に同じ間隙比にはなりません。
voidRatio = 0.75

# 目標空隙率：粒子間の空隙の体積と全体の体積（粒子の体積＋空隙の体積）の比を示す値です。これは間隙比から計算されます。
target_porosity = voidRatio / (1 + voidRatio)
print('\nTarget Porosity: {:.3f}'.format(target_porosity))


### 載荷プロセス全体に関する定数・変数 ###
# 0:圧密、1:圧密(密度調整)、2:繰り返しせん断(Forward)、3:繰り返しせん断(Backward)の状態管理をするための変数です。
stage_index = 0

# 予め生成しておいた粒子の配置を記入したファイルを読み込むかどうかのフラグです
flag_import_pack_file = True


### 圧密に関する定数・変数 ###
# 圧密時の初期摩擦角：圧密時に意図的に内部摩擦角を落とすことによって、密な供試体を作成します。
# もし一回目の圧密で所定の間隙比に到達しなかった場合には、少しずつ間隙比を下げていき再圧密を行います。。
frictangle_consolidation = 25 / 180 * np.pi

# 圧密時の目標応力：等方的に圧密される際に達成したい応力の大きさを表す値です。単位はPaです。
consolidation_stress = 100e3

# 圧密時の最大ひずみ速度：粒子が圧密される際の最大のひずみ速度を表す値です。
consolidation_max_strain_rate = 4000

# 速度勾配テンソル：圧密時の境界の速度の変化を表すテンソルです。
# この値が大きいほど、境界の位置は急速に変化します。
consolidation_velGrad = Matrix3(-consolidation_max_strain_rate, 0, 0,
                                0, -consolidation_max_strain_rate, 0,
                                0, 0, -consolidation_max_strain_rate)

# 圧密の終了判定を行うための閾値です。
consolidation_thres_ratio = 0.99

# 一回摩擦係数を落とした後何ステップ分放置するかを計算するための変数です。
cur_iter = 0


### 繰り返しせん断に関する定数・変数 ###

# 繰り返しせん断時の反転を応力で定義するか、ひずみで定義するかを決めます。Trueがひずみ定義です。
flag_strain_reversal = False
cyclic_loading_max_strain_rate = 20    # 繰り返しせん断時での最大ひずみ速度です。
cyclic_loading_velGrad_forward = Matrix3(0, 0, cyclic_loading_max_strain_rate,
                                         0, 0, 0,
                                         0, 0, 0)
cyclic_loading_velGrad_backward = Matrix3(0, 0, -cyclic_loading_max_strain_rate,
                                          0, 0, 0,
                                          0, 0, 0)

# 繰り返しせん断時の目標最大せん断ひずみ振幅です。：0.05→5%
cyclic_shear_strain_amplitude = 0.002

# 繰り返しせん断時の目標最大せん断応力振幅です。：15kPa=15×10^3Pa
cyclic_shear_stress_amplitude = 15e3

# 目標の繰り返し回数です。
target_num_cycle = 100

# 現時点での繰り返し回数です。
current_num_cycle = 0

# 目標の両振幅せん断ひずみです。：0.075→7.5%
target_double_amplitude_shear_strain = 0.5

# 現時点での両振幅せん断歪です。
current_double_amplitude_shear_strain = 0

# 反転時のせん断ひずみを保存しておくための変数です。
prev_shear_strain = 0


### 出力に関する定数・変数 ###

# 出力ファイルにヘッダーが生成されたかどうかのフラグ
flag_header_done = False

# 出力ファイルを出力する間隔
output_iter_interval = 10

# エネルギーのキーを保存しておくための変数です。
temp_energy_keys = []

# 後処理用のファイルを記録するかどうかのフラグです。
flag_record_VTK = True

# 後処理用のファイルを何ステップごとに記録するか
record_VTK_interval = 500


############## 結果を格納するフォルダの確認と生成 ##############
# 結果を保存するためのファイルとフォルダを作成します。
dt_start = datetime.datetime.now()
print("Start simulation started at " +
      dt_start.strftime('%Y/%m/%d %H:%M:%S.%f'))

output_folder_path = Path(os.path.abspath(
    os.path.dirname(sys.argv[0]))).parent / "result" / dt_start.strftime('%Y-%m-%d_%H-%M-%S')
output_folder_path.mkdir(exist_ok=True)
output_file_path = output_folder_path / \
    (dt_start.strftime('%Y-%m-%d_%H-%M-%S') + "_output.csv")

# 粒子の配列を保存しておくファイルとフォルダを作成します。
temp_folder_path = Path(os.path.abspath(
    os.path.dirname(sys.argv[0]))).parent / "temp"
temp_folder_path.mkdir(exist_ok=True)
temp_sp_file_path = temp_folder_path / "temp.txt"


############## 粒子と接触モデルの定義 ##############
# 粒子単体の接触モデルを決めます。今回は一番単純なFrictMatを使用します。
mat_sp = FrictMat(young=young, poisson=poisson,
                  frictionAngle=frictangle, density=density)
O.materials.append(mat_sp)

# 粒子を生成するコードです。
# 過去に同じ粒子を生成したことがある場合には、flag_import_pack_fileをTrueにすると、作成時間が短縮できます。
pack_sp = pack.SpherePack()
if flag_import_pack_file:
    pack_sp.load(str(temp_sp_file_path))
    O.periodic = True
    O.cell.hSize = Matrix3(maxCorner_x, 0, 0, 0,
                           maxCorner_y, 0, 0, 0, maxCorner_z)
else:
    pack_sp.makeCloud((0, 0, 0), (maxCorner_x, maxCorner_y, maxCorner_z),
                      rMean=rMean, rRelFuzz=rRelFuzz, periodic=True,
                      seed=-1)
    pack_sp.save(str(temp_sp_file_path))

# 上のコードで生成した粒子をOmegaインスタンスに渡します。
pack_sp.toSimulation()
print('Number of Particles: ' + str(len(O.bodies)) +', Current Porosity: {:.3f}'.format(utils.porosity()))

# 解析の際の時間ステップを決めるコードです。
O.dt = .1 * PWaveTimeStep()


############## エンジンの定義 ##############

if flag_record_VTK:
    O.engines = [
        ForceResetter(),
        InsertionSortCollider(
            [Bo1_Sphere_Aabb(), Bo1_Box_Aabb()]),
        InteractionLoop(
            [Ig2_Sphere_Sphere_ScGeom(), Ig2_Box_Sphere_ScGeom()],
            [Ip2_FrictMat_FrictMat_FrictPhys()],
            [Law2_ScGeom_FrictPhys_CundallStrack()]
        ),
        NewtonIntegrator(damping=0.2),
        VTKRecorder(fileName=str(output_folder_path)+'/3d-vtk-', recorders=['all'], iterPeriod=record_VTK_interval),
        PyRunner(iterPeriod=1, command="checkState()"),
        PyRunner(iterPeriod=output_iter_interval, command="addPlotData()")
    ]
else:
    O.engines = [
        ForceResetter(),
        InsertionSortCollider(
            [Bo1_Sphere_Aabb(), Bo1_Box_Aabb()]),
        InteractionLoop(
            [Ig2_Sphere_Sphere_ScGeom(), Ig2_Box_Sphere_ScGeom()],
            [Ip2_FrictMat_FrictMat_FrictPhys()],
            [Law2_ScGeom_FrictPhys_CundallStrack()]
        ),
        NewtonIntegrator(damping=0.2),
        PyRunner(iterPeriod=1, command="checkState()"),
        PyRunner(iterPeriod=output_iter_interval, command="addPlotData()")
    ]

# エネルギーを計算するためのフラグを立てます。
O.trackEnergy = True

# 圧密用の速度勾配テンソルを代入します。
O.cell.velGrad = consolidation_velGrad

# 状態遷移用の関数です
def checkState():

    # 最初に定義した変数の中で、シミュレーション中に変わるものをglobal変数として明示しておきます。
    global stage_index, current_num_cycle, cur_iter, prev_shear_strain, current_double_amplitude_shear_strain

    # 応力とひずみに関するパラメータを取得します。
    [s00, s01, s02], [_, s11, s12], [_, _, s22] = getStress()
    [e00, e01, e02], [_, e11, e12], [_, _, e22] = O.cell.trsf

    # 平均主応力を計算します。
    mean_stress = -(s00 + s11 + s22) / 3

    # 圧密の場合の処理です。
    if stage_index == 0:

        # 平均主応力によって速度勾配テンソルを変化させます。
        O.cell.velGrad = consolidation_velGrad * \
            (1 - mean_stress / consolidation_stress)

        # 平均主応力が所定の応力を超えた状態で次の状態に移行
        # その際に粒子の内部摩擦角を0.9倍にして若干滑りやすい状態→密度が上昇しやすい状態にする
        if mean_stress >= consolidation_stress * consolidation_thres_ratio:
            stage_index = 1
            setContactFriction(O.materials[0].frictionAngle * 0.9)
            cur_iter = O.iter
            addPlotData()


    # 圧密(密度調節)の場合の処理です。
    elif stage_index == 1:

        # 平均主応力によって速度勾配テンソルを変化させます。
        O.cell.velGrad = consolidation_velGrad * \
            (1 - mean_stress / consolidation_stress) * 0.1

        # 500ステップ回っていないと、次のステージに進むか現在のステージにとどまるかの判定ができないようにします。
        flag_consolidation_stabilize = (O.iter - cur_iter > 500)

        if flag_consolidation_stabilize:

            # ここで3つの検証をします。
            # flag_consolidation_stress：ここでは平均主応力が所定の応力を超えた状態かどうかをチェックしています。
            # flag_consolidation_porosity：ここでは与えた間隙比(空隙率)よりも密になっているかどうかをチェックしています。
            # flag_consolidation_force：準静的状態かどうかを見るために非平衡力を見ています。
            flag_consolidation_stress = mean_stress >= consolidation_stress * \
                consolidation_thres_ratio
            flag_consolidation_porosity = utils.porosity() <= target_porosity
            flag_consolidation_force = utils.unbalancedForce() < 0.2


            if flag_consolidation_stress and flag_consolidation_force:

                if flag_consolidation_porosity:
                    print(
                        "Consolidation has finished! Now proceeding to cyclic forward loading")
                    print('Current Porosity: {:.3f}'.format(utils.porosity()))

                    stage_index = 2

                    setContactFriction(frictangle)
                    O.cell.velGrad = cyclic_loading_velGrad_forward
                    prev_shear_strain = e02

                    addPlotData()

                else:
                    setContactFriction(O.materials[0].frictionAngle * 0.9)
                    cur_iter = O.iter

    elif stage_index == 2:

        if current_double_amplitude_shear_strain < abs(e02 -  prev_shear_strain):
            current_double_amplitude_shear_strain = abs(e02 -  prev_shear_strain)

        if current_num_cycle > target_num_cycle or current_double_amplitude_shear_strain > target_double_amplitude_shear_strain:
            print("Cyclic loading has just finished!")
            finish_simulation()

        else:
            if flag_strain_reversal:
                flag_reversal = e02 > cyclic_shear_strain_amplitude
            else:
                flag_reversal = s02 > cyclic_shear_stress_amplitude

            if flag_reversal:
                print("Current Cycle: " + str(current_num_cycle), end="")

                stage_index = 3
                current_num_cycle += 0.5
                O.cell.velGrad = cyclic_loading_velGrad_backward

                print(" Next Backward Cycle: " + str(current_num_cycle))

                addPlotData()

    elif stage_index == 3:

        if current_double_amplitude_shear_strain < abs(e02 -  prev_shear_strain):
            current_double_amplitude_shear_strain = abs(e02 -  prev_shear_strain)

        if current_num_cycle > target_num_cycle or current_double_amplitude_shear_strain > target_double_amplitude_shear_strain:
            print("Cyclic loading has just finished!")
            finish_simulation()

        else:
            if flag_strain_reversal:
                flag_reversal = e02 < -cyclic_shear_strain_amplitude
            else:
                flag_reversal = s02 < -cyclic_shear_stress_amplitude

            if flag_reversal:
                print("Current Cycle: " + str(current_num_cycle), end="")

                stage_index = 2
                current_num_cycle += 0.5
                O.cell.velGrad = cyclic_loading_velGrad_forward

                print(" Next Forward Cycle: " + str(current_num_cycle))

                addPlotData()


# 載荷が終了した際に呼ばれる関数です。
def finish_simulation():
    addPlotData()

    O.pause()


# 図化のための関数です。
def addPlotData():
    global flag_header_done, stage_index, current_num_cycle, temp_energy_keys

    i = O.iter
    [s00, s01, s02], [_, s11, s12], [_, _, s22] = getStress() / \
        1000  # addPlotData()だけkPaに変換する
    [e00, e01, e02], [_, e11, e12], [_, _, e22] = O.cell.trsf
    e00 = 1 - e00
    e11 = 1 - e11
    e22 = 1 - e22

    temp_porosity = utils.porosity()
    temp_void_ratio = temp_porosity / (1 - temp_porosity)
    temp_unbalanced_force = utils.unbalancedForce()
    temp_friction_angle = O.materials[0].frictionAngle
    temp_coord_num = utils.avgNumInteractions()
    
    [f00, f01, f02], [f10, f11, f12], [f20, f21, f22] = utils.fabricTensor()[0]

    # 平均応力 (圧縮が正に変換)
    mean_stress = -(s00 + s11 + s22) / 3
    # ミーゼスの相当応力(偏差応力テンソルの第2次不変量J2の平方根を√3倍したもの)
    deviatoric_stress = ((((s00 - s11) ** 2 + (s11 - s22) ** 2 + (s22 - s00)
                         ** 2) / 6 + s01 ** 2 + s12 ** 2 + s02 ** 2) * 3) ** (1 / 2)

    print('prog: ' + str(stage_index) + ' - {:07}'.format(i),
          ' p:{:>7.2f}'.format(mean_stress),
          ' q:{:>7.2f}'.format(deviatoric_stress),
          ' s02:{:>7.2f}'.format(s02),
          ' s22:{:>7.2f}'.format(s22),
          ' e02:{:>10.6f}'.format(e02),
          ' e22:{:>7.3f}'.format(e22),
          ' poro:{:> 7.4f}'.format(temp_porosity),
          ' UnF:{:> 5.2f}'.format(temp_unbalanced_force),
          ' FricAng:{:> 6.3f}'.format(temp_friction_angle)
          )


    plot.addData(i=i,
                 s00=s00,
                 s22=s22,
                 s02=s02,
                 e00=e00,
                 e22=e22,
                 e02=e02)

    # 出力データを準備します
    energy_dict = dict(O.energy.items())

    energy_values = list(energy_dict.values())
    output_values = [i, O.time, stage_index, current_num_cycle, temp_void_ratio,
                     temp_unbalanced_force, temp_friction_angle, temp_coord_num,
                     s00, s11, s22, s12, s02, s01,
                     e00, e11, e22, e12, e02, e01, 
                     f00, f01, f02, f10, f11, f12, f20, f21, f22] + energy_values
    output_values_str = ""

    for temp in output_values:
        output_values_str += str(temp) + ","

    output_values_str = output_values_str[:-1] + "\n"
    with open(output_file_path, 'a') as f:
        f.write(output_values_str)

    if not flag_header_done or len(temp_energy_keys) < len(list(energy_dict.keys())):
        temp_energy_keys = list(energy_dict.keys())

        with open(output_file_path, 'r') as f:
            lines = f.readlines()

        key_list = "step,time(s),stage,number_of_cyclic,void_ratio,unbalanced_force(N),friction_angle(rad),coordination_number,s00(kPa),s11(kPa),s22(kPa),s12(kPa),s02(kPa),s01(kPa),e00,e11,e22,e12,e02,e01,f00,f01,f02,f10,f11,f12,f20, f21,f22"

        energy_dict = dict(O.energy.items())
        for temp in list(energy_dict.keys()):
            key_list += "," + temp + "(N⋅m)"
        key_list += "\n"

        lines[0] = key_list

        with open(output_file_path, 'w') as f:
            f.writelines(lines)


plot.plots = {"i": ("s00", "s22", "s02"),
              "i ": ("e00", "e22", "e02"),
              " e02": ("s02"),
              " s22 ": ("s02")}

plot.plot()