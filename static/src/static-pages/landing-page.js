angular.module('staticPages', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function($routeProvider) {
        $routeProvider.when('/', {
            templateUrl: "static-pages/landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })


    .config(function($routeProvider) {
        $routeProvider.when('/about', {
            templateUrl: "static-pages/about.tpl.html",
            controller: "AboutPageCtrl"
        })
    })

    .config(function($routeProvider) {
        $routeProvider.when('/login', {
            templateUrl: "static-pages/login.tpl.html",
            controller: "LoginPageCtrl"
        })
    })



    .controller("AboutPageCtrl", function($scope, $sce, $http, ngProgress){

    })


    .controller("LoginPageCtrl", function($scope, $sce, $http, ngProgress){
        console.log("login page controller is running!")

    })

    .controller("LandingPageCtrl", function($scope, $auth, ngProgress){
        console.log("landing page!")
        ngProgress.complete()



        $scope.newUser = {
            givenName: "",
            familyName: "",
            email: "",
            password: ""
        };

    })










