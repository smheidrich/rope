"""
This module serves to convert a data structure composed of Python primitives
(dict, list, tuple, int, str, None) to JSON-serializable primitives (object,
array, number, str, null).

A core feature of this serializer is that the produced will round-trip to
identical objects when deserialized by the standard library json module.
In other words, this property always holds:

    >>> original_data = ... any JSON ...
    >>> encoded = python_to_json(original_data)
    >>> serialized = json.dumps(encoded)
    >>> decoded = json.loads(serialized)
    >>> rehydrated_data = json_to_python(decoded)

    >>> assert rehydrated_data == original_data
    >>> assert encoded == decoded

Couple challenges in straight serialization that this module helps resolve:

- json.dumps() maps both Python list and tuple to JSON array. This module
  converts Python list `[1, 2, 3]` as-is and converts Python tuple `(1, 2, 3)`
  to special object construct `{"$": "t", "items": [1, 2, 3]}`

- Python dict keys can be a tuple/dict, but JSON Object keys must be strings
  This module replaces all `dict` keys with `refid` which can be resolved using
  the `encoded["references"][refid]` lookup table. Except there's a small
  optimisation, if the dict key is a string that isn't only numeric, which is
  encoded directly into the object.

- Python dict keys cannot be another dict because it is unhashable, therefore
  there's no encoding for having objects as keys either.

- There is currently no support for floating point numbers.

Note that `json_to_python` only accepts Python objects that can be the output
of `python_to_json`, there is NO guarantee for going the other way around. This
may or may not work:

    >>> python_to_json(json_to_python(original_data)) == original_data

"""


def python_to_json(o, version=1):
    assert version in (1, 2)
    references = []
    return {
        "v": 1,
        "data": _py2js(o, references, version=version),
        "references": references,
    }


def json_to_python(o):
    version = o["v"]
    assert version in (1, 2)
    references = o["references"]
    data = _js2py(o["data"], references, version)
    return data


def _py2js(o, references, version):
    if isinstance(o, (str, int)) or o is None:
        return o
    elif isinstance(o, tuple):
        return {"$": "t", "items": [_py2js(item, references, version) for item in o]}
    elif isinstance(o, list):
        return [_py2js(item, references, version) for item in o]
    elif isinstance(o, dict):
        result = {}
        for k, v in o.items():
            if k == "$":
                raise ValueError('dict cannot contain reserved key "$"')
            if isinstance(k, str) and not k.isdigit():
                result[k] = _py2js(v, references, version)
            else:
                assert isinstance(k, (str, int, list, tuple)) or k is None
                refid = len(references)
                references.append(_py2js(k, references, version))
                result[str(refid)] = _py2js(v, references, version)
        return result
    raise TypeError(f"Object of type {type(o)} is not allowed {o}")


def _js2py(o, references, version):
    assert not isinstance(o, tuple)
    if isinstance(o, (str, int)) or o is None:
        return o
    elif isinstance(o, list):
        return list(_js2py(item, references, version) for item in o)
    elif isinstance(o, dict):
        result = {}
        if "$" in o:
            if o["$"] == "t":
                data = o["items"]
                return tuple(_js2py(item, references, version) for item in data)
            raise TypeError(f'Unrecognized object of type: {o["$"]} {o}')
        else:
            for refid, v in o.items():
                assert isinstance(refid, str)
                if refid.isdigit():
                    refid = int(refid)
                    assert 0 <= refid < len(references)
                    k = references[refid]
                    result[_js2py(k, references, version)] = _js2py(v, references, version)
                else:
                    result[refid] = _js2py(v, references, version)
        return result
    raise TypeError(f"Object of type {type(o)} is not allowed {o}")
