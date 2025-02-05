import subprocess
import os

import pandas as pd
import pytest

from mitosheet.mito_backend import get_mito_frontend_code
from mitosheet.tests.test_utils import create_mito_wrapper_dfs


STRINGS_TO_TEST = [
    ('Normal'),
    ('space in the text'),
    ('学	医'),
    ('this\is\text'),
    ('\n'),
    ('\t'),
    ('\r')
]


# Skip if not not defined
@pytest.mark.skipif(os.system("node -v") != 0, reason='Node not defined')
@pytest.mark.parametrize('string', STRINGS_TO_TEST)
def test_mito_frontend_is_valid_code(tmp_path, string):
    df = pd.DataFrame({'A': [string]})
    mito = create_mito_wrapper_dfs(df)
    frontend_code = get_mito_frontend_code('1', '2', '3', mito.mito_backend)
    
    file = tmp_path / 'out.js'
    with open(file, 'w+') as f:
        f.write(frontend_code)

    p = subprocess.Popen(['node', file,], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (output, err) = p.communicate()
    exit_code = p.wait()

    print(output, err)

    # we want to make sure that there are no failures in parsing, that it runs up to the 
    # ReferenceError: document is not defined 
    assert 'SyntaxError' not in err.decode('utf-8') 
    assert 'ReferenceError' in err.decode('utf-8') 




    