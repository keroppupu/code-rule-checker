       IDENTIFICATION DIVISION.
       PROGRAM-ID. EMPCALC.
      *=============================================================*
      * 社員情報計算プログラム（Shift_JIS文字コード規約検証用サンプル）
      * 日本語全角文字および半角カナの混在確認
      *=============================================================*
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-EMP-INFO.
           05  WS-EMP-ID          PIC X(05).
           05  WS-EMP-NAME        PIC X(20).
           05  WS-EMP-KANA        PIC X(20).
           05  WS-SALARY          PIC 9(08) COMP.
       01  WS-DISP-MSG            PIC N(20).
       PROCEDURE DIVISION.
       MAIN-PROC.
      * 日本語文字列の設定（Shift_JISバイト長検証）
           MOVE "10001" TO WS-EMP-ID.
           MOVE "山田太郎" TO WS-EMP-NAME.
           STOP RUN.
