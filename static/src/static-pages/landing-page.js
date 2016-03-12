angular.module('staticPages', [
    'ngRoute',
    'satellizer',
    'currentUserService',
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
        $routeProvider.when('/login', {
            templateUrl: "static-pages/login.tpl.html",
            controller: "LoginPageCtrl"
        })
    })


    .controller("AboutPageCtrl", function ($scope, $sce, $http) {

    })


    .controller("LoginPageCtrl", function ($scope, $sce, $http) {
        console.log("login page controller is running!")

    })

    .controller("LandingPageCtrl", function ($scope, $http, $auth, $location, CurrentUser) {
        console.log("landing page!")


        $scope.authenticate = function () {
            console.log("authenticate!")

            $auth.authenticate("orcid")
                .then(function(){
                    console.log("you have successfully logged in!")
                })
                .catch(function(error){
                    console.log("there was an error logging in:", error)
                })
        };



    })










