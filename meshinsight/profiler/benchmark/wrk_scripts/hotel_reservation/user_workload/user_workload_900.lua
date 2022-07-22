require "socket"
math.randomseed(socket.gettime()*1000)
math.random(); math.random(); math.random()

-- scale to packet size: 
-- 1-100 13-200 25-300 37-400 49-500 61-600 74-700 87-800 99-900 111-1000 122-1100 133-1200 145-1300 157-1400


local function user_login()
  local method = "GET"
  -- local path = "http://localhost:5000/user?username=uw_1100&password=123&number=1100"
  local path = "http://localhost:5000/user?username=uw_99&password=123&number=99"
  local headers = {}
  -- headers["Content-Type"] = "application/x-www-form-urlencoded"
  return wrk.format(method, path, headers, nil)
end

request = function()
    return user_login()
end
