import json
from core.error_code import err


def create_response(additional_info=None, json_dump=False):
    response = {
        "status": "success",
    }
    if additional_info:
        response.update(additional_info)
        if json_dump:
            return json.dumps(response)
        return response
    if json_dump:
        return json.dumps(response)
    return response


def create_error_dict(code, fax_tran_id=None):
    if code == 200:
        resp_code = code
        code = 200
    desc = ""
    if isinstance(code, list):
        for code_val in code:
            desc = desc + err[code_val] + ","
        if desc:
            desc = desc[:-1]
    else:
        desc = err[code]
    if fax_tran_id is not None:
        return {"resp_code": code, "description": desc, "data": code, "fax_tran_id": fax_tran_id}
    return {"resp_code": code, "description": desc, "data": code}
