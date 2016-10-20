angular.module('app', [

    // external libs
    'ngRoute',
    'ngMessages',
    'ngCookies',
    'ngResource',
    'ngSanitize',
    'ngMaterial',
    'ngProgress',

    // this is how it accesses the cached templates in ti.js
    'templates.app',

    // services
    'numFormat',

    // pages
    "landing"

]);




angular.module('app').config(function ($routeProvider,
                                       $mdThemingProvider,
                                       $locationProvider) {
    $locationProvider.html5Mode(true);
    $mdThemingProvider.theme('default')
        .primaryPalette('deep-orange')
        .accentPalette("blue")



});


angular.module('app').run(function($route,
                                   $rootScope,
                                   $q,
                                   $timeout,
                                   $cookies,

                                   $http,
                                   $location) {

    //
    //(function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
    //        (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
    //    m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
    //})(window,document,'script','//www.google-analytics.com/analytics.js','ga');
    //ga('create', 'UA-23384030-1', 'auto');




    $rootScope.$on('$routeChangeStart', function(next, current){
    })
    $rootScope.$on('$routeChangeSuccess', function(next, current){
        //window.scrollTo(0, 0)
        //ga('send', 'pageview', { page: $location.url() });

    })



    $rootScope.$on('$routeChangeError', function(event, current, previous, rejection){
        console.log("$routeChangeError! here's some things to look at: ", event, current, previous, rejection)

        $location.url("page-not-found")
        window.scrollTo(0, 0)
    });
});



angular.module('app').controller('AppCtrl', function(
    ngProgressFactory,
    $rootScope,
    $scope,
    $route,
    $location,
    NumFormat,
    $http,
    $mdDialog,
    $sce){

    var progressBarInstance = ngProgressFactory.createInstance();

    $rootScope.progressbar = progressBarInstance
    $scope.progressbar = progressBarInstance
    $scope.numFormat = NumFormat
    $scope.moment = moment // this will break unless moment.js loads over network...

    $scope.global = {}

    $scope.pageTitle = function(){
        if (!$scope.global.title){
            $scope.global.title = "Discover the online impact of your research"
        }
        return "Impactstory: " + $scope.global.title
    }


    $rootScope.$on('$routeChangeSuccess', function(next, current){
        $scope.global.template = current.loadedTemplateUrl
            .replace("/", "-")
            .replace(".tpl.html", "")
        $scope.global.title = null
    })

    $scope.trustHtml = function(str){
        return $sce.trustAsHtml(str)
    }

    var showAlert = function(msgText, titleText, okText){
        if (!okText){
            okText = "ok"
        }
          $mdDialog.show(
                  $mdDialog.alert()
                    .clickOutsideToClose(true)
                    .title(titleText)
                    .textContent(msgText)
                    .ok(okText)
            );
    }
    $rootScope.showAlert = showAlert
})
















angular.module('landing', [
    'ngRoute',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/', {
            templateUrl: "landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/landing/:landingPageName', {
            templateUrl: "landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })

    .controller("LandingPageCtrl", function ($scope,
                                             $http,
                                             $timeout) {

        console.log("i am the landing page ctrl")
        $scope.main = {
            step: "no-doi"
        }

        $scope.animation = null

        var animate = function(step){
            $scope.animation = step + "start"
            console.log("set animation", $scope.animation)
            $timeout(function(){
                $scope.animation = step + "finish"
                console.log("set animation", $scope.animation)
            }, 505)
        }

        var baseUrl = "http://api.oadoi.org/v1/publication/doi/"
        $scope.exampleDoi = "10.1016/j.tree.2007.03.007"

        $scope.$watch(function(s){return s.main.doi }, function(newVal, oldVal){
            console.log("doi change", newVal, oldVal)
            if (!newVal){
                return false
            }
            if (newVal.indexOf("10.") === 0) {
                animate(1)
                $http.get(baseUrl + newVal)
                    .success(function(resp){
                        console.log("got response back", resp.results[0])
                        if (newVal == $scope.exampleDoi){
                            console.log("this is the sample DOI...waiting to return result.")
                            $timeout(function(){
                                console.log("returning the result now")
                                animate(2)
                                $scope.main.resp = resp.results[0]
                            }, 5000)
                        }
                        else {
                            animate(2)
                            $scope.main.resp = resp.results[0]
                        }


                    })
            }
        })

    })











angular.module("numFormat", [])

    .factory("NumFormat", function($location){

        var commas = function(x) { // from stackoverflow
            if (!x) {
                return x
            }
            var parts = x.toString().split(".");
            parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            return parts.join(".");
        }


        var short = function(num, fixedAt){
            if (typeof num === "string"){
                return num  // not really a number
            }

            // from http://stackoverflow.com/a/14994860/226013
            if (num === null){
                return 0
            }
            if (num === 0){
                return 0
            }

            if (num >= 1000000) {
                return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
            }
            if (num >= 100000) { // no decimal if greater than 100thou
                return (num / 1000).toFixed(0).replace(/\.0$/, '') + 'k';
            }

            if (num >= 1000) {
                return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
            }


            if (num < 1) {
                return Math.round(num * 100) / 100;  // to two decimals
            }

            return Math.ceil(num);
        }

        var round = function(num){
            return Math.round(num)
        }

        var doubleUrlEncode = function(str){
            return encodeURIComponent( encodeURIComponent(str) )
        }

        // from http://cwestblog.com/2012/09/28/javascript-number-getordinalfor/
        var ordinal = function(n) {
            n = Math.round(n)
            var s=["th","st","nd","rd"],
                v=n%100;
            return n+(s[(v-20)%10]||s[v]||s[0]);
        }

        var decimalToPerc = function(decimal, asOrdinal){
            var ret = Math.round(decimal * 100)
            if (asOrdinal){
                ret = ordinal(ret)
            }
            return ret
        }
        return {
            short: short,
            commas: commas,
            round: round,
            ordinal: ordinal,
            doubleUrlEncode: doubleUrlEncode,
            decimalToPerc: decimalToPerc

        }
    });
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
