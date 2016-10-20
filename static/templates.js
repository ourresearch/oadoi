angular.module('templates.app', ['landing.tpl.html']);

angular.module("landing.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("landing.tpl.html",
    "<div class=\"top-screen\" layout=\"row\" layout-align=\"center center\">\n" +
    "    <div class=\"content\">\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "        <div class=\"no-doi demo-step\"\n" +
    "             ng-class=\"{'animated fadeOutDown': animation}\"\n" +
    "             ng-show=\"!animation\">\n" +
    "            <h1>Find open-access versions of scholarly articles</h1>\n" +
    "            <div class=\"input-row\">\n" +
    "                <md-input-container class=\"md-block\" flex-gt-sm=\"\">\n" +
    "                    <label>Paste a DOI here</label>\n" +
    "                    <input ng-model=\"main.doi\">\n" +
    "              </md-input-container>\n" +
    "            </div>\n" +
    "            <div class=\"example-doi\">\n" +
    "                <span class=\"label\">example: </span>\n" +
    "                <span class=\"val\">{{ exampleDoi }}</span>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "\n" +
    "        <div class=\"has-doi animated fadeInDown demo-step\"\n" +
    "             ng-class=\"{'animated fadeOutDown': animation=='2start'}\"\n" +
    "             ng-show=\"animation=='1finish'\">\n" +
    "            <h2>\n" +
    "                This <span class=\"us\">oadoi.org</span> URL links to fulltext where available:\n" +
    "            </h2>\n" +
    "\n" +
    "            <div class=\"our-url\">\n" +
    "                <a href=\"http://oadoi.org/{{ main.doi }}\">\n" +
    "                    <span class=\"http\">http://</span><span class=\"domain\">oadoi.org</span><span class=\"doi\">/{{ main.doi }}</span>\n" +
    "                </a>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "\n" +
    "        <div class=\"has-results animated fadeInDown demo-step\"\n" +
    "             ng-show=\"animation=='2finish'\">\n" +
    "\n" +
    "            <pre>{{ main.resp | json }}</pre>\n" +
    "        </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "    </div>\n" +
    "</div>");
}]);
