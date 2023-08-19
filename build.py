#!/usr/bin/env python3
# @author Sin0n0me

import os
import json
import subprocess
import glob
from urllib.request import urlretrieve

SETTING_FILE_NAME = 'build_setting.json'
SOLUTION_LIST_FILE_NAME = 'solution_list.txt'

KEY_MSBUILD_PATH = 'MSBuild path'
KEY_BUILD = 'Build'
KEY_BUILD_SOLUTION_PATH = 'Solution path'
KEY_BUILD_RESTORE_NUGET = 'Restore package'
KEY_BUILD_IGNORE_UPDATE = 'Ignore update'
KEY_BUILD_SETTING = 'Build settings'
KEY_BUILD_SETTING_CONFIGURATION = 'Configuration'
KEY_BUILD_SETTING_PLATFORM = 'Platform'

# MSBuile.exeがありそうな場所のリスト
MSBUILED_PATH_LIST = [
    'C:/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin',
    'C:/Program Files (x86)/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin',
    'C:/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/17.0/Bin',
    'C:/Program Files (x86)/Microsoft Visual Studio/2022/Community/MSBuild/17.0/Bin',
]

# NuGet
NUGET_DOWNLOAD_URL = 'https://dist.nuget.org/win-x86-commandline/latest/nuget.exe'
NUGET_EXE_FILE_NAME = 'nuget.exe'


# 保存
def save_setting_file(setting_dict):
    with open(SETTING_FILE_NAME, 'w') as file:
        json.dump(setting_dict, file, indent=2)


def add_solution(key: str, path: str):
    with open(SETTING_FILE_NAME, 'r') as file:
        settings = json.load(file)

    solution = {
        key: {
            KEY_BUILD_SOLUTION_PATH: path,
            KEY_BUILD_RESTORE_NUGET: False,
            KEY_BUILD_IGNORE_UPDATE: False,
            KEY_BUILD_SETTING: {
                KEY_BUILD_SETTING_CONFIGURATION: [],
                KEY_BUILD_SETTING_PLATFORM: [],
            }
        }
    }

    settings[KEY_BUILD].update(solution)
    save_setting_file(settings)


# 初期化
def init_setting_json():
    if not os.path.exists(SETTING_FILE_NAME):
        with open(SETTING_FILE_NAME, 'w') as file:
            json.dump({}, file, indent=2)

    setting_dict = {}

    # MSBuild.exeの検索
    for path in MSBUILED_PATH_LIST:
        if os.path.exists(f'{path}/MSBuild.exe'):
            setting_dict[KEY_MSBUILD_PATH] = path
            break

    setting_dict[KEY_BUILD] = {}

    save_setting_file(setting_dict)


# slnファイルのあるパスを全て取得
def load_solution_list():
    # ビルド設定ファイルが存在しなければ作成
    exist_file = os.path.exists(SETTING_FILE_NAME)
    if not exist_file:
        init_setting_json()

    with open(SETTING_FILE_NAME, 'r') as file:
        settings = json.load(file)

    with open(SOLUTION_LIST_FILE_NAME, 'r') as file:
        lines = file.readlines()

    for line in lines:
        if line == '':
            continue

        # 改行コードを消す
        line = line.replace('\r', '')
        line = line.replace('\n', '')

        if not os.path.exists(line):
            continue

        # 末尾が/の場合は後続処理で面倒になるので外す
        line = line.replace('\\', '/')
        if line[-1] == '/':
            line = line[:-1]

        sln_files = glob.glob(f'{line}/*.sln', recursive=True)
        for sln_path in sln_files:
            sln_path = sln_path.replace('\\', '/')
            key = sln_path.split('/')[-1].split('.')[0]

            # 既に追加されている場合は何もしない
            if exist_file and key in settings[KEY_BUILD]:
                continue

            add_solution(key, sln_path)


# Nugetパッケージの復元
def restore_nuget_package(setting_dict: dict):
    # nuget.exeが存在しない場合ダウンロード
    if not os.path.exists(NUGET_EXE_FILE_NAME):
        urlretrieve(NUGET_DOWNLOAD_URL, NUGET_EXE_FILE_NAME)

    # 復元
    for key in setting_dict[KEY_BUILD].keys():
        build_dict = setting_dict[KEY_BUILD][key]

        # 既に復元済みならば何もしない
        if build_dict[KEY_BUILD_RESTORE_NUGET]:
            continue

        try:
            command = ['nuget.exe', 'restore',
                       build_dict[KEY_BUILD_SOLUTION_PATH]]
            subprocess.run(command, check=True)
            setting_dict[KEY_BUILD][key][KEY_BUILD_RESTORE_NUGET] = True
        except subprocess.CalledProcessError as e:
            print(e)

    # 更新
    save_setting_file(setting_dict)


# ビルド設定の取得
def get_build_config(setting_dict: dict):
    for key in setting_dict[KEY_BUILD].keys():
        build_dict = setting_dict[KEY_BUILD][key]

        # 既に復元済みならば何もしない
        if build_dict[KEY_BUILD_IGNORE_UPDATE]:
            continue

        # slnからconfigurationとplatformを抽出
        configuration_list = []
        platform_list = []
        lines = ''
        section_start: bool = False

        with open(build_dict[KEY_BUILD_SOLUTION_PATH], mode='r', encoding="utf-8") as sln:
            lines = sln.readlines()

        for line in lines:
            if 'GlobalSection(SolutionConfigurationPlatforms)' in line:
                section_start = True
                continue

            if 'EndGlobalSection' in line:
                section_start = False
                break

            if section_start:
                # タブ文字取り除き  \t\tWinDebug|x64 = WinDebug|x64 -> WinDebug|x64 = WinDebug|x64
                line = line.replace('\t', '')
                # スペース取り除き  WinDebug|x64 = WinDebug|x64 -> WinDebug|x64=WinDebug|x64
                line = line.replace(' ', '')
                # =で分割          WinDebug|x64=WinDebug|x64 -> [WinDebug|x64][WinDebug|x64]
                line = line.split('=')
                # |でさらに分割     WinDebug|x64 -> [WinDebug][x64]
                line = line[0].split('|')

                configuration_list.append(line[0])
                platform_list.append(line[1])

        configuration_list = list(set(configuration_list))
        platform_list = list(set(platform_list))
        setting_dict[KEY_BUILD][key][KEY_BUILD_SETTING][KEY_BUILD_SETTING_CONFIGURATION] = configuration_list
        setting_dict[KEY_BUILD][key][KEY_BUILD_SETTING][KEY_BUILD_SETTING_PLATFORM] = platform_list

    # 更新
    save_setting_file(setting_dict)


# ビルド
def build(setting_dict: dict):
    for key in setting_dict[KEY_BUILD].keys():
        build_dict = setting_dict[KEY_BUILD][key]
        build_setting_dict = build_dict[KEY_BUILD_SETTING]

        for configuration in build_setting_dict[KEY_BUILD_SETTING_CONFIGURATION]:
            for platform in build_setting_dict[KEY_BUILD_SETTING_PLATFORM]:

                sln_file_path = build_dict[KEY_BUILD_SOLUTION_PATH]
                sln_dir = os.path.dirname(sln_file_path)
                command = [
                    f'{setting_dict[KEY_MSBUILD_PATH]}/MSBuild.exe',
                    sln_file_path,
                    f'/t:build',
                    f'/p:configuration={configuration}',
                    f'/p:Platform={platform}',
                    f'/fileLoggerParameters:LogFile={sln_dir}/BuildLog/{configuration}_{platform}_build.log;Verbosity=minimal'
                ]

                try:
                    subprocess.run(command, check=True)
                except subprocess.CalledProcessError as e:
                    print(e)


def main():
    # リスト読み込み
    load_solution_list()

    with open(SETTING_FILE_NAME, 'r') as file:
        settings = json.load(file)

    # 復元
    restore_nuget_package(settings)

    # configuration platform の取得
    get_build_config(settings)

    # ビルド
    build(settings)


if __name__ == '__main__':
    main()
    print('終了するにはEnterを押してください')
    input()  # pauseの代わり
