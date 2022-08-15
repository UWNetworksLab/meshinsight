local function req()
  local method = "POST"
  local str = string.rep("123", 950)
  local path = "http://10.96.88.88:80/" .. str
  local headers = {}
  return wrk.format(method, path, headers, str)
end

request = function()
    return req()
end
