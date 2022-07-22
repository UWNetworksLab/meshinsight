require "socket"


local function reserve()
  local method = "GET"
  local path = "http://localhost:5000/reservation?inDate=2015-04-21&outDate=2015-04-23&lat=nil&lon=nil&hotelId=uw_123&customerName=cornell123&username=cornell123&password=1234&number=12000" 
  local headers = {}
  -- headers["Content-Type"] = "application/x-www-form-urlencoded"
  return wrk.format(method, path, headers, nil)
end


request = function()
  return reserve()
end
