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

    .controller("LandingPageCtrl", function ($scope,
                                             $mdDialog,
                                             $rootScope,
                                             $timeout) {
        $scope.global.showFooter = false;
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










