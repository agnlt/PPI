import ast
import os
import glob
import time
import json

from PyLog.logger import Logger
from levenshtein import lev

# Type alias to represent a function.
# Looks like this:
# function = {
#     'fucntion name': '...',
#     'function args': ['arg1', 'arg2'],
#     'file in which the function is': 'file.py',
#     'line in the file where the function is': '12' 
# }
FunctionType = dict[str, list[str], str, str]

STDLIB_IGNORE = ['test', 'site-packages', 'lib2to3']
JSON_OUTPUT = 'functions.json'

logger = Logger()

def read_source_file(filename: os.PathLike) -> str:
    """
    Retrieves the content of the `filename`. Used to parse a Python file.
    """
    with open(filename, 'r') as source:
        return source.read()


def save_json(content: list, filename: str = JSON_OUTPUT) -> None:
    """
    Save the `content` (Python dict) to the `filename`. By default, the filename is `JSON_OUTPUT`.
    """
    data = json.dumps(content, indent=4)
    with open(filename, 'w') as out:
        print(data, file=out)


def read_json_file(filename: str = JSON_OUTPUT) -> dict:
    """
    Returns the content of the `filename` (must be a JSON file).
    """
    with open(filename) as f:
        return json.load(f)
        

def get_signature(function: dict, file_infos: bool = False) -> str:
    """
    Returns the function signature from a `function` dict.
    """
    args = ''
    for a in function['args']:
        args += str(a) + ', '
    signature = f"{function['name']}({args[:-2]})"
    if file_infos:
        signature = f"{function['filename']}:{function['line']} " + signature
    return signature


def get_function_from_node(node: ast.AST, file_path: os.PathLike, abspath: bool = False) -> FunctionType:
    """
    Returns a `FunctionType` object from an `ast.AST` node.
    """
    name = node.name
    args = node.args.args
    new_function = {
        'name': name,
        'args': [arg.arg for arg in args],
        'filename': file_path if not abspath else os.path.abspath(file_path),
        'line': node.lineno,
    }
    return new_function


def normalize(query: str) -> str:
    """
    Universal format for a function signature and an user query.
    The format is `function_name_separated_with_underscored ( arg1, arg2, arg3 )`. 
    The number of spaces does not matter, which means that `is zipfile (filename)` and `is    zipfile ( filename)` 
    will both produce the same output, e. g `is_zipfile ( filename )`.
    """
    split_query = query.split('(')
    name = split_query[0] # everything brefore the opening parenthesis
    name = '_'.join([a for a in name.split(' ') if a != ''])
    args = split_query[1].replace(')', '')
    args = ', '.join([a.lstrip().rstrip() for a in args.split(',')])
    return f'{name} ( {args} )'


def index_folder(base_folder: os.PathLike, folders_to_ignore: list[str] = []) -> list[FunctionType]:
    """
    Index the `base_folder` while ignoring the `folder_to_ignore` list. See `STDLIB_IGNORE` for the defaults folders that will be ignored.
    When the indexing is done, the functions that have been parsed are saved to the `JSON_OUTPUT` file by default.
    If the file already exists when the function is called, the `base_folder` is not indexed and the content of the file is returned.
    """
    # before indexing, check if there is the JSON file functions.json
    logger.warning(f'Not indexing {base_folder}, reading the content of {JSON_OUTPUT}. If you want to avoid this behaviour, either delete or rename {JSON_OUTPUT}.')
    if os.path.exists(JSON_OUTPUT):
        return read_json_file(JSON_OUTPUT)

    functions = []
    folders_to_ignore += STDLIB_IGNORE
    start = time.time()
    for filename in glob.iglob(f'{base_folder}/**', recursive=True):
        current_dir = filename.split('/')
        # https://stackoverflow.com/questions/3170055/test-if-lists-share-any-items-in-python (for 👇)
        want_to_continue = filename.endswith('py') and not bool(set(current_dir) & set(folders_to_ignore))
        if os.path.isfile(filename) and want_to_continue:
            logger.info(f'Reading {filename}...')
            source_code = read_source_file(filename)
            logger.info(f'Parsing {filename}...')
            parsed = ast.parse(source_code)
            # go through the AST
            for node in ast.walk(parsed):
                # no constructors
                if isinstance(node, ast.FunctionDef) and not node.name.startswith('__'):
                    new_function = get_function_from_node(node, filename)
                    functions.append(new_function)
    # save the results to a JSON file
    logger.info(f'Saving the results to {JSON_OUTPUT}...')
    save_json(content=functions)
    end = time.time()
    logger.info(f'Indexed folder {base_folder} in {end - start} seconds.')
    return functions


def sort(query: str, functions: list[FunctionType]) -> list:
    """
    Sort the functions using the `levenshtein.lev()` function.
    """
    sorted_functions = []
    for f in functions:
        sorted_functions.append((lev(query, normalize(get_signature(f))), f))
    return sorted(sorted_functions, key=lambda x: x[0])


if __name__ == '__main__':
    query = normalize('mainloop()')

    functions = sort(query, index_folder('./stdlib'))

    for i in range(10):
        print(get_signature(functions[i][1], True))