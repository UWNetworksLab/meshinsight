require "socket"

local function recommend()
  local method = "GET"
  local path = "http://localhost:5000/recommendations?require=rate&lat=38.0235&lon=-122.095" 
  local headers = {}
  -- headers["Content-Type"] = "application/x-www-form-urlencoded"
  return wrk.format(method, path, headers, nil)
end


request = function()
  return recommend()
end
