require "socket"


local function get_user()
  local id = math.random(0, 500)
  local user_name = "Cornell_" .. tostring(id)
  local pass_word = ""
  for i = 0, 9, 1 do
    pass_word = pass_word .. tostring(id)
  end
  return user_name, pass_word
end

local function user_login()
  local user_name, password = get_user()
  local method = "GET"
  local path = "http://localhost:5000/user?username=" .. user_name .. "&password=" .. password
  local headers = {}
  headers["A"] = "application/x-www-form-urlencoded"
  headers["B"] = "application/x-www-form-urlencoded"
  headers["C"] = "application/x-www-form-urlencoded"
  headers["D"] = "application/x-www-form-urlencoded"
  headers["E"] = "application/x-www-form-urlencoded"
  headers["F"] = "application/x-www-form-urlencoded"
  return wrk.format(method, path, headers, nil)
end

request = function()
    return user_login()
end
