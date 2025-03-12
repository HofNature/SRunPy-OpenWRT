# module 名称
module("luci.controller.srunpy", package.seeall)

function index()
    entry({"admin", "services", "srunpy"}, cbi("srunpy"), _("SRun Client"), 1)
end
