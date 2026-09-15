# SCSPTranslationData

[![License](https://mirrors.creativecommons.org/presskit/buttons/88x31/svg/by-nc-sa.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh)



- SCSP 简体中文翻译数据仓库。

当前维护分支为 `TransData`。本仓库只保存公开的翻译数据与相关辅助文件，不包含游戏客户端、账号信息、运行日志、抓包、私有服务端或本地运行环境。

## 与插件仓库的关系

- 公开插件仓库：[kohakunamori/scsp-localify](https://github.com/kohakunamori/scsp-localify)
- `scsp-localify` 通过 `resources/schinese` Git submodule 固定引用本仓库的已验证翻译版本。
- 翻译文件保持 `scsp_localify/...` 目录结构，供插件直接打包或加载。
- 与客户端保存、离线服务、个人环境有关的内容不属于本仓库，也不应提交到本仓库。



# 贡献翻译

## 获取原文

- 前往 [DumpData](https://github.com/kohakunamori/SCSPTranslationData/tree/DumpData) 分支寻找。
- 或使用 [scsp-localify 的文本 Dump 功能](https://github.com/kohakunamori/scsp-localify#%E8%87%AA%E8%A1%8C-dump-%E5%8E%9F%E6%96%87) 获取当前客户端实际原文（推荐）。
  - `DumpData` 可能落后于当前客户端；提交译文前应尽量确认原文仍然匹配。



## 提交翻译

- 找到您想翻译的文件，将其翻译后，以 **相同路径** 提交 Pull requests 到本分支即可。
- 初始提交的文本为机翻润色，仅用于抛砖引玉。**之后不允许提交机翻文本**。



### 机翻润色文件表

- 修改这些部分不需要经过我的同意。提交更改时，请将对应部分从下表删除。当下表为空后，可以删除 `机翻润色文件表`。

| 文件                                                         | 内容                                                         | 备注           |
| ------------------------------------------------------------ | ------------------------------------------------------------ | -------------- |
| `scsp_localify`/`local2.json`                                | 全部                                                         | -              |
| `scsp_localify`/`localify.json`                              | `mlMaintenance_TextFormatTile`<br>`mlMenu_Button`<br>`mlMenu_Header` | 其它部分未翻译 |
| `scsp_localify`/`scenario`/`s40`/`04040000`/`s40_04040000_01.json`<br>`scsp_localify`/`scenario`/`s40`/`04040000`/`s40_04040000_02.json` | 全部                                                         | -              |





# 贡献者（GitHub）
<a href="https://github.com/ShinyGroup/SCSPTranslationData/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=ShinyGroup/SCSPTranslationData" />
</a>
