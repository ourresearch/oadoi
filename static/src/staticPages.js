angular.module('staticPages', [
    'ngRoute',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/api', {
            templateUrl: "api.tpl.html",
            controller: "StaticPageCtrl"
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/about', {
            templateUrl: "about.tpl.html",
            controller: "StaticPageCtrl"
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/team', {
            templateUrl: "team.tpl.html",
            controller: "StaticPageCtrl"
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/browser-tools', {
            templateUrl: "browser-tools.tpl.html",
            controller: "StaticPageCtrl"
        })
    })

    .controller("StaticPageCtrl", function ($scope,
                                             $http,
                                             $rootScope,
                                             $timeout) {


        $scope.global.title = $scope.global.template

        console.log("static page ctrl")
        $timeout(function(){
            console.log("highlight?")
            if ($scope.global.template.indexOf("api") >= 0){
                console.log("yes, highlight!")
                hljs.initHighlighting();
            }

        }, 0)

    })










