require("luci.sys")

m = Map("srunpy", translate("深澜网关"), translate("OpenWRT 平台下的深澜网关客户端"))

s = m:section(TypedSection, "srunpy", translate("服务设置"))
s.addremove = false
s.anonymous = true

enable = s:option(Flag, "enable", translate("启用"))
running = s:option(DummyValue, "_running", translate("运行状态"))
running.rawhtml = true
function running.cfgvalue(self, section)
    local pid = luci.sys.exec("cat /var/run/srunpy.pid 2>/dev/null")
    if pid and pid ~= "" then
        local running = luci.sys.exec("ps -p " .. pid .. " | grep " .. pid)
        if running and running ~= "" then
            return "<span style='color:green'>" .. translate("正在运行") .. "</span>"
        end
    end
    return "<span style='color:red'>" .. translate("未在运行") .. "</span>"
end
host = s:option(Value, "host", translate("服务地址"))
prot = s:option(ListValue, "protcol", translate("服务协议"))
prot:value("https", "http")
sleeptime = s:option(Value, "sleeptime", translate("检测间隔"))
sleeptime.datatype = "uinteger"
verify = s:option(Flag, "ssl_verify", translate("验证SSL"))

a = m:section(TypedSection, "account", translate("账户设置"))
a.addremove = false
a.anonymous = true

username = a:option(Value, "username", translate("用户名"))
username.rmempty = false
pass = a:option(Value, "password", translate("密码"))
pass.password = true
pass.rmempty = false

local apply = luci.http.formvalue("cbi.apply")
if apply then
    io.popen("/etc/init.d/srunpy stop > /dev/null && /etc/init.d/srunpy start > /dev/null &")
end

return m