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
        $routeProvider.when('/login', {
            templateUrl: "static-pages/login.tpl.html",
            controller: "LoginCtrl"
        })
    })


    .controller("AboutPageCtrl", function ($scope, $sce, $http) {

    })


    .controller("LoginCtrl", function ($scope) {
        console.log("kenny loggins page controller is running!")
        $scope.global.loggingIn = true

    })

    .controller("LandingPageCtrl", function ($scope,
                                             $mdDialog,
                                             $rootScope,
                                             $timeout) {
        $scope.global.showBottomStuff = false;
        console.log("landing page!", $scope.global)

        var orcidModalCtrl = function($scope){
            console.log("IHaveNoOrcidCtrl ran" )
            $scope.modalAuth = function(){
                $rootScope.authenticate("orcid-register")
            }
        }

        $scope.noOrcid = function(){
            $mdDialog.show({
                controller: orcidModalCtrl,
                templateUrl: 'orcid-dialog.tmpl.html',
                clickOutsideToClose:true
            })


        }

    })
    .controller("IHaveNoOrcidCtrl", function($scope){
        console.log("IHaveNoOrcidCtrl ran" )
    })










