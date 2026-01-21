#!/usr/bin/env python
from bancos.brou.parser import depurar_archivo

# Simular POST file object
class FakeFile:
    def __init__(self, path):
        self.filename = path
        self.file = open(path, 'rb')
    
    def read(self):
        return self.file.read()
    
    def seek(self, pos):
        return self.file.seek(pos)

try:
    fake_file = FakeFile('static/ejemplo_estado_cuenta.xls')
    result = depurar_archivo(fake_file)
    
    if isinstance(result, tuple):
        df, error = result
        print(f'ERROR: {error}')
        print(f'DF is None: {df is None}')
    else:
        df = result
        print(f'DF type: {type(df)}')
        if df is not None:
            print(f'DF shape: {df.shape}')
            print(f'Columns: {list(df.columns)}')
            if len(df) > 0:
                print('First row OK')
            else:
                print('DF is empty')
        else:
            print('DF is None')
except Exception as e:
    import traceback
    print(f'EXCEPTION: {e}')
    traceback.print_exc()
