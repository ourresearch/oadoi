angular.module('packagePage', [
    'directives.badge',
    'ngRoute'
])



    .config(function($routeProvider) {
        $routeProvider.when('/package/:language/:package_name', {
            templateUrl: 'package-page/package-page.tpl.html',
            controller: 'PackagePageCtrl',
            resolve: {
                packageResp: function($http, $route, PackageResource){
                    return PackageResource.get({
                        namespace: $route.current.params.language,
                        name: $route.current.params.package_name
                    }).$promise
                }
            }
        })
    })



    .controller("PackagePageCtrl", function($scope,
                                            $routeParams,
                                            ngProgress,
                                            FormatterService,
                                            packageResp){
        ngProgress.complete()
        $scope.package = packageResp
        $scope.format = FormatterService
        $scope.depNode = packageResp.rev_deps_tree

        console.log("package page!", $scope.package)

        $scope.apiOnly = function(){
            alert("Sorry, we're still working on this! In the meantime, you can view the raw data via our API.")
        }










    })



