# jupyter 前置作業

由於直接下載`ipykernel`會出現:
```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.
langchain-core 1.2.7 requires packaging<26.0.0,>=23.2.0, but you have packaging 26.0 which is incompatible.
```
需要進行降級動作

## 流程

首先，進入虛擬環境

```
source .venv/bin/activate
pip install packaging==25.0.0 --force-reinstall
pip install ipykernel -U
```

最後，進入`.ipynb`檔案，選擇核心`.venv`作為interpreter的環境，即完成