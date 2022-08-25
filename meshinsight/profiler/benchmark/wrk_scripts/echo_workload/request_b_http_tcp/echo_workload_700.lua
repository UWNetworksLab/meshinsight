-- curl 10.96.88.88:80
-- ./wrk/wrk -t1 -c1 -d 60s http://10.96.88.88:80 --latency -s echo-server/echo_workload.lua


local function req()
  local method = "POST"
  local str = string.rep("123", 205)
  --local path = "http://10.96.88.88:80/" .. str
  local path = "http://10.96.88.88:80/"
  local headers = {}
  return wrk.format(method, path, headers, str)
end

request = function()
    return req()
end
