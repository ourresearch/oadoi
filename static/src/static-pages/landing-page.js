angular.module('staticPages', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/', {
            templateUrl: "static-pages/landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })


    .config(function ($routeProvider) {
        $routeProvider.when('/about', {
            templateUrl: "static-pages/about.tpl.html",
            controller: "AboutPageCtrl"
        })
    })


    .config(function ($routeProvider) {
        $routeProvider.when('/loggins', {
            templateUrl: "static-pages/loggins.tpl.html",
            controller: "LogginsPageCtrl"
        })
    })


    .controller("AboutPageCtrl", function ($scope, $sce, $http) {

    })


    .controller("LogginsPageCtrl", function ($scope) {
        console.log("loggins page controller is running!")
        $scope.global.showFooter = false;

    })

    .controller("LandingPageCtrl", function ($scope, $rootScope, $http, $auth, $location) {
        $scope.global.showFooter = false;
        console.log("landing page!", $scope.global)




    })










